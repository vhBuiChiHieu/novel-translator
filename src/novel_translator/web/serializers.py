from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from novel_translator.application.dtos import DashboardDTO, ModelCallDTO
from novel_translator.config import ProjectSettings

SENSITIVE_KEYS = {"api_key", "authorization", "secret", "token", "password", "cookie"}


def redact_sensitive(value: Any, secrets: Iterable[str] = ()) -> Any:
    secret_values = tuple(secret for secret in secrets if secret)
    if isinstance(value, dict):
        return {
            str(key): "[redacted]" if str(key).lower() in SENSITIVE_KEYS else redact_sensitive(item, secret_values)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item, secret_values) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive(item, secret_values) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        result = value
        for secret in secret_values:
            result = result.replace(secret, "[redacted]")
        return result
    return value


def safe_settings(settings: ProjectSettings) -> dict[str, Any]:
    """Serialize settings without the excluded SecretStr credential."""
    model = settings.model.model_dump(exclude={"api_key"}, mode="json")
    return {
        "project_name": settings.project_name,
        "title": settings.title,
        "source_language": settings.source_language,
        "target_language": settings.target_language,
        "genre": settings.genre,
        "model": model,
        "prompt_version": settings.prompt_version,
        "chunk": settings.chunk.model_dump(mode="json"),
        "continuity": settings.continuity.model_dump(mode="json"),
        "context": settings.context.model_dump(mode="json"),
        "validation": settings.validation.model_dump(mode="json"),
        "log_level": settings.log_level,
    }


def safe_model_call(call: ModelCallDTO, settings: ProjectSettings) -> dict[str, Any]:
    api_key = settings.model.api_key.get_secret_value() if settings.model.api_key else ""
    return redact_sensitive(call.model_dump(mode="json"), (api_key,))


def safe_dashboard(dashboard: DashboardDTO) -> dict[str, Any]:
    data = dashboard.model_dump(mode="json")
    data.pop("project_path", None)
    return redact_sensitive(data)


def safe_path(path: Path) -> str:
    """Return a path only for an authenticated, project-scoped response."""
    return str(path.resolve())
