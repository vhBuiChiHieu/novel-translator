from __future__ import annotations

from typing import Any

import httpx

from novel_translator.infrastructure.model.provider import ProviderDiagnostic

MAX_BODY_CHARS = 32_000
SENSITIVE_KEYS = {"api_key", "authorization", "secret", "token"}


def response_diagnostic(provider: str, response: httpx.Response, message: str) -> ProviderDiagnostic:
    try:
        body: object = _sanitize(response.json())
    except ValueError:
        body = response.text[:MAX_BODY_CHARS]
    return ProviderDiagnostic(
        provider=provider,
        message=message,
        status_code=response.status_code,
        body=body,
        truncated=len(response.content) > MAX_BODY_CHARS,
    )


def error_diagnostic(provider: str, message: str) -> ProviderDiagnostic:
    return ProviderDiagnostic(provider=provider, message=message)


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[redacted]" if str(key).lower() in SENSITIVE_KEYS else _sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, str):
        return value[:MAX_BODY_CHARS]
    if isinstance(value, (bool, float, int)) or value is None:
        return value
    return str(value)[:MAX_BODY_CHARS]
