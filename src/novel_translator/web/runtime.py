from __future__ import annotations

import asyncio
import hmac
import secrets
import threading
from collections import deque
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import Request
from fastapi.encoders import jsonable_encoder

from novel_translator.application.facade import ApplicationFacade
from novel_translator.application.services.project_service import ProjectService
from novel_translator.application.services.translation_service import TranslationProgress

from .errors import ProjectBusyError, WebError, map_exception, safe_error
from .serializers import redact_sensitive

SESSION_COOKIE = "novel_local_session"
EVENT_BUFFER_SIZE = 500


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class EventRecord:
    id: int
    event: str
    data: dict[str, Any]


class EventBroker:
    """Thread-safe event buffer shared by worker threads and SSE clients."""

    def __init__(self, max_events: int = EVENT_BUFFER_SIZE) -> None:
        self._events: deque[EventRecord] = deque(maxlen=max_events)
        self._next_id = 1
        self._closed = False
        self._condition = threading.Condition()

    def publish(self, event: str, data: dict[str, Any]) -> EventRecord:
        encoded = jsonable_encoder(data)
        with self._condition:
            if self._closed:
                return EventRecord(0, "closed", {})
            record = EventRecord(self._next_id, event, encoded)
            self._next_id += 1
            self._events.append(record)
            self._condition.notify_all()
            return record

    def since(self, last_event_id: int | None) -> tuple[list[EventRecord], bool]:
        with self._condition:
            if not self._events:
                return [], False
            oldest = self._events[0].id
            stale = last_event_id is not None and last_event_id < oldest - 1
            return [event for event in self._events if last_event_id is None or event.id > last_event_id], stale

    def wait_since(self, last_event_id: int | None, timeout: float = 15.0) -> tuple[list[EventRecord], bool]:
        with self._condition:
            if self._closed:
                return [], False
            events, stale = self.since(last_event_id)
            if events or stale:
                return events, stale
            self._condition.wait(timeout)
            return self.since(last_event_id)

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()


@dataclass
class Operation:
    kind: str
    project_path: Path
    chapter_numbers: list[int] = field(default_factory=list)
    operation_id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "queued"
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    cancel_requested: bool = False
    future: Future[Any] | None = field(default=None, repr=False)

    def is_cancel_requested(self) -> bool:
        return self.cancel_requested

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "kind": self.kind,
            "status": self.status,
            "chapter_numbers": self.chapter_numbers,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }


class WebRuntime:
    """Owns local session state and serializes all project mutations."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="novel-web-operation")
        self._operations: dict[str, Operation] = {}
        self._active_operation_id: str | None = None
        self._project_path: Path | None = None
        self._recent_projects: list[Path] = []
        self._startup_error: list[str] = []
        self._startup_token = secrets.token_hex(32)
        self._session_token = secrets.token_urlsafe(32)
        self._bootstrap_used = False
        self._closed = False
        self.broker = EventBroker()

    @property
    def startup_token(self) -> str:
        return self._startup_token

    @property
    def session_token(self) -> str:
        return self._session_token

    @property
    def startup_error(self) -> list[str]:
        with self._lock:
            return list(self._startup_error)

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def project_path(self) -> Path | None:
        with self._lock:
            return self._project_path

    @property
    def recent_projects(self) -> list[str]:
        with self._lock:
            return [str(path) for path in self._recent_projects]

    def set_startup_error(self, errors: list[str]) -> None:
        with self._lock:
            self._startup_error = list(errors)

    def bootstrap(self, token: str | None) -> None:
        with self._lock:
            if not token or self._bootstrap_used or not hmac.compare_digest(token, self._startup_token):
                raise WebError(401, "BOOTSTRAP_INVALID", "The local launch token is invalid or expired.")
            self._bootstrap_used = True

    def require_session(self, request: Request) -> None:
        cookie = request.cookies.get(SESSION_COOKIE)
        if not cookie or not hmac.compare_digest(cookie, self._session_token):
            raise WebError(401, "SESSION_REQUIRED", "Bootstrap the local app before calling this endpoint.")
        self._validate_loopback_headers(request)

    def validate_loopback_request(self, request: Request) -> None:
        self._validate_loopback_headers(request)

    @staticmethod
    def _validate_loopback_headers(request: Request) -> None:
        host = request.headers.get("host", "").split(":", 1)[0].strip("[]").lower()
        if host not in {"127.0.0.1", "localhost"}:
            raise WebError(403, "INVALID_HOST", "This local app only accepts loopback requests.")
        origin = request.headers.get("origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost"}:
                raise WebError(403, "INVALID_ORIGIN", "This local app only accepts loopback origins.")

    def open_project(self, path: Path) -> None:
        if not path.expanduser().is_absolute():
            raise WebError(422, "PROJECT_PATH_INVALID", "Project path must be absolute.")
        project_path = path.expanduser().resolve()
        errors = ProjectService().validate(project_path)
        if errors:
            raise WebError(422, "PROJECT_INVALID", "The selected directory is not a valid project.", {"errors": errors})
        with self._lock:
            self._raise_if_busy()
            ApplicationFacade(project_path)
            self._project_path = project_path
            self._startup_error = []
            self._recent_projects = [project_path, *(item for item in self._recent_projects if item != project_path)][:10]

    def create_project(self, parent: Path, name: str) -> Path:
        if not parent.expanduser().is_absolute():
            raise WebError(422, "PROJECT_PARENT_INVALID", "Project parent path must be absolute.")
        parent_path = parent.expanduser().resolve()
        if not parent_path.is_dir():
            raise WebError(422, "PROJECT_PARENT_INVALID", "Project parent directory does not exist.")
        if name != name.strip() or name in {".", ".."} or Path(name).name != name:
            raise WebError(422, "PROJECT_NAME_INVALID", "Project name must be a single folder name.")
        if any(character in name for character in '<>:"/\\|?*'):
            raise WebError(422, "PROJECT_NAME_INVALID", "Project name contains invalid path characters.")
        with self._lock:
            self._raise_if_busy()
        project_path = parent_path / name
        try:
            ProjectService().init(parent_path, name)
        except FileExistsError as error:
            raise WebError(409, "PROJECT_EXISTS", "A project with this name already exists.") from error
        except OSError as error:
            raise WebError(422, "PROJECT_CREATE_FAILED", "The project could not be created.") from error
        self.open_project(project_path)
        return project_path

    def current_facade(self) -> ApplicationFacade:
        with self._lock:
            path = self._project_path
        if path is None:
            raise WebError(409, "PROJECT_NOT_OPEN", "No project is open.")
        return ApplicationFacade(path)

    def current_path(self) -> Path:
        with self._lock:
            if self._project_path is None:
                raise WebError(409, "PROJECT_NOT_OPEN", "No project is open.")
            return self._project_path

    def get_operation(self, operation_id: str) -> Operation:
        with self._lock:
            operation = self._operations.get(operation_id)
        if operation is None:
            raise WebError(404, "OPERATION_NOT_FOUND", "Operation was not found.")
        return operation

    def submit(
        self,
        kind: str,
        work: Callable[[Operation], object],
        chapter_numbers: list[int] | None = None,
    ) -> Operation:
        with self._lock:
            if self._closed:
                raise WebError(503, "SERVER_SHUTTING_DOWN", "The local server is shutting down.")
            path = self._project_path
            if path is None:
                raise WebError(409, "PROJECT_NOT_OPEN", "No project is open.")
            self._raise_if_busy()
            operation = Operation(kind=kind, project_path=path, chapter_numbers=chapter_numbers or [])
            self._operations[operation.operation_id] = operation
            self._active_operation_id = operation.operation_id
            operation.future = self._executor.submit(self._run_operation, operation, work)
            return operation

    def _raise_if_busy(self) -> None:
        if self._active_operation_id is None:
            return
        active = self._operations.get(self._active_operation_id)
        if active and active.status in {"queued", "running", "cancelling"}:
            raise ProjectBusyError(active.operation_id)
        self._active_operation_id = None

    def _run_operation(self, operation: Operation, work: Callable[[Operation], object]) -> None:
        with self._lock:
            operation.status = "running"
            operation.started_at = utc_now()
        self._publish_operation(operation, "operation_started")
        try:
            result = work(operation)
            with self._lock:
                operation.result = redact_sensitive(jsonable_encoder(result)) if result is not None else {}
                operation.status = "completed"
                operation.completed_at = utc_now()
            self._publish_operation(operation, "operation_completed")
        except Exception as error:
            mapped = map_exception(error)
            with self._lock:
                operation.error = safe_error(error)
                operation.status = "cancelled" if mapped.code == "OPERATION_CANCELLED" else "failed"
                operation.completed_at = utc_now()
            self._publish_operation(operation, "operation_cancelled" if operation.status == "cancelled" else "operation_failed")
        finally:
            with self._lock:
                if self._active_operation_id == operation.operation_id:
                    self._active_operation_id = None

    def _publish_operation(self, operation: Operation, event: str) -> None:
        event_result = (
            {key: value for key, value in operation.result.items() if key != "output_path"}
            if operation.result
            else operation.result
        )
        data = {
            "operation_id": operation.operation_id,
            "event": event,
            "kind": operation.kind,
            "status": operation.status,
            "chapter_numbers": operation.chapter_numbers,
            "result": event_result,
            "error": operation.error,
            "at": iso_now(),
        }
        self.broker.publish(event, data)

    def publish_progress(self, operation: Operation, progress: TranslationProgress) -> None:
        self.broker.publish(
            progress.event,
            {
                "operation_id": operation.operation_id,
                "event": progress.event,
                "chapter_number": progress.chapter_number,
                "chunk_index": progress.chunk_index,
                "total_chunks": progress.total_chunks,
                "duration_ms": progress.duration_ms,
                "error": progress.error,
                "at": iso_now(),
            },
        )

    def cancel(self, operation_id: str) -> Operation:
        operation = self.get_operation(operation_id)
        with self._lock:
            if operation.status not in {"queued", "running"}:
                return operation
            operation.cancel_requested = True
            operation.status = "cancelling"
        self._publish_operation(operation, "operation_cancelling")
        return operation

    async def wait(self, operation: Operation) -> Operation:
        if operation.future is not None:
            await asyncio.wrap_future(operation.future)
        return operation

    def operation_result_or_raise(self, operation: Operation) -> object:
        if operation.status in {"failed", "cancelled"}:
            error = operation.error or {"code": "OPERATION_FAILED", "message": "Operation failed", "details": {}}
            code = str(error.get("code", "OPERATION_FAILED"))
            status = {
                "PROVIDER_ERROR": 502,
                "VALIDATION_ERROR": 422,
                "NOT_FOUND": 404,
                "SOURCE_CHANGED": 409,
                "PROJECT_BUSY": 409,
            }.get(code, 500)
            raise WebError(status, code, str(error.get("message", "Operation failed")), error.get("details", {}))
        return operation.result or {}

    def events_for(self, last_event_id: str | None) -> Iterator[EventRecord]:
        try:
            last_id = int(last_event_id) if last_event_id else None
        except ValueError:
            last_id = None
        while not self._closed:
            events, stale = self.broker.wait_since(last_id)
            if stale:
                record = self.broker.publish(
                    "resync_required",
                    {"event": "resync_required", "reason": "event_buffer_expired", "at": iso_now()},
                )
                yield record
                last_id = record.id
                continue
            if not events:
                yield EventRecord(0, "keepalive", {})
                continue
            for event in events:
                yield event
                last_id = event.id

    def close(self) -> None:
        with self._lock:
            self._closed = True
        self.broker.close()
        self._executor.shutdown(wait=True, cancel_futures=False)
