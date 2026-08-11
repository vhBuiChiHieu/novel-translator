from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from novel_translator.application.services.project_service import ProjectNotFoundError
from novel_translator.application.services.translation_service import (
    ChapterNotFoundError,
    SourceChangedError,
    TranslationCancelledError,
)
from novel_translator.infrastructure.model.exceptions import ModelProviderError


@dataclass
class WebError(Exception):
    status_code: int
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def as_response(self) -> dict[str, object]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class ProjectBusyError(WebError):
    def __init__(self, operation_id: str | None = None) -> None:
        super().__init__(
            status_code=409,
            code="PROJECT_BUSY",
            message="Another project operation is already running.",
            details={"operation_id": operation_id} if operation_id else {},
        )


def map_exception(error: Exception) -> WebError:
    if isinstance(error, WebError):
        return error
    if isinstance(error, TranslationCancelledError):
        return WebError(409, "OPERATION_CANCELLED", "Operation stopped after the current chunk.")
    if isinstance(error, ProjectNotFoundError):
        return WebError(422, "PROJECT_INVALID", str(error))
    if isinstance(error, ChapterNotFoundError):
        return WebError(404, "CHAPTER_NOT_FOUND", str(error))
    if isinstance(error, SourceChangedError):
        return WebError(409, "SOURCE_CHANGED", str(error))
    if isinstance(error, ModelProviderError):
        return WebError(502, "PROVIDER_ERROR", "The model provider operation failed safely.")
    if isinstance(error, FileNotFoundError):
        return WebError(404, "NOT_FOUND", str(error))
    if isinstance(error, ValueError):
        message = str(error)
        lowered = message.lower()
        if "not found" in lowered or "was not found" in lowered:
            return WebError(404, "NOT_FOUND", message)
        return WebError(422, "VALIDATION_ERROR", message)
    if isinstance(error, RuntimeError) and "no project is open" in str(error).lower():
        return WebError(409, "PROJECT_NOT_OPEN", "No project is open.")
    return WebError(500, "INTERNAL_ERROR", "The local operation failed.")


def safe_error(error: Exception) -> dict[str, object]:
    mapped = map_exception(error)
    return mapped.as_response()["error"]  # type: ignore[return-value]
