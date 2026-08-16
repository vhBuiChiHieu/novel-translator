from __future__ import annotations

import json
import logging
from pathlib import Path

from novel_translator.infrastructure.model.provider import (
    ModelProvider,
    ProviderAttempt,
    ProviderDiagnostic,
    ProviderMetrics,
)
from novel_translator.schemas.translation_request import TranslationRequest
from novel_translator.schemas.translation_response import TranslationResponse

logger = logging.getLogger(__name__)


def write_raw_prompt(project_path: Path, job_id: int, chunk_id: int, request: TranslationRequest) -> None:
    """Write the rendered prompt used for one translation chunk."""

    path = _chunk_log_directory(project_path, job_id, chunk_id) / "raw-prompt.txt"
    _write_text(
        path,
        "===== SYSTEM PROMPT =====\n"
        f"{request.system_prompt}\n\n"
        "===== USER PROMPT =====\n"
        f"{request.user_prompt}\n",
    )


def write_raw_responses(
    project_path: Path,
    job_id: int,
    chunk_id: int,
    provider: ModelProvider,
    response: TranslationResponse | None = None,
    error: BaseException | None = None,
) -> None:
    """Write one sanitized raw response file for every provider attempt."""

    attempts = list(getattr(provider, "last_attempts", None) or [])
    if attempts:
        for index, attempt in enumerate(attempts):
            diagnostic = getattr(attempt, "diagnostic", None)
            _write_response(
                project_path,
                job_id,
                chunk_id,
                attempt,
                diagnostic,
                response if index == len(attempts) - 1 else None,
                error if index == len(attempts) - 1 else None,
            )
        return

    diagnostic = getattr(provider, "last_diagnostic", None)
    fallback_attempt = ProviderAttempt(
        attempt_number=1,
        status="failed" if error is not None else "completed",
        metrics=getattr(provider, "last_metrics", ProviderMetrics()),
        diagnostic=diagnostic,
    )
    _write_response(project_path, job_id, chunk_id, fallback_attempt, diagnostic, response, error)


def _write_response(
    project_path: Path,
    job_id: int,
    chunk_id: int,
    attempt: ProviderAttempt,
    diagnostic: ProviderDiagnostic | None,
    response: TranslationResponse | None,
    error: BaseException | None,
) -> None:
    payload: dict[str, object] = {
        "attempt_number": attempt.attempt_number,
        "status": attempt.status,
    }
    if diagnostic is not None:
        payload.update(diagnostic.model_dump())
    elif response is not None:
        payload["parsed_response"] = response.model_dump(exclude_none=True)
    if error is not None:
        payload["error"] = {"type": type(error).__name__, "message": str(error)}
    path = (
        _chunk_log_directory(project_path, job_id, chunk_id)
        / f"raw-response-attempt-{attempt.attempt_number:02d}.json"
    )
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")


def _chunk_log_directory(project_path: Path, job_id: int, chunk_id: int) -> Path:
    return project_path / "logs" / "jobs" / f"job-{job_id:06d}" / f"chunk-{chunk_id:06d}"


def _write_text(path: Path, content: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError:
        logger.exception("Could not write raw model debug file path=%s", path)
