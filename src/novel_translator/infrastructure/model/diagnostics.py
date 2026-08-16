from __future__ import annotations

from typing import Any

import httpx

from novel_translator.infrastructure.model.provider import ProviderDiagnostic

MAX_BODY_CHARS = 32_000
SENSITIVE_KEYS = {"api_key", "apikey", "x-goog-api-key", "authorization", "secret", "token"}


def response_diagnostic(
    provider: str,
    response: httpx.Response,
    message: str,
    secrets: tuple[str, ...] = (),
) -> ProviderDiagnostic:
    try:
        body: object = _sanitize(response.json(), secrets)
    except ValueError:
        body = _sanitize(response.text[:MAX_BODY_CHARS], secrets)
    return ProviderDiagnostic(
        provider=provider,
        message=message,
        status_code=response.status_code,
        body=body,
        truncated=len(response.content) > MAX_BODY_CHARS,
    )


def error_diagnostic(provider: str, message: str) -> ProviderDiagnostic:
    return ProviderDiagnostic(provider=provider, message=message)


def _sanitize(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[redacted]" if str(key).lower() in SENSITIVE_KEYS else _sanitize(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item, secrets) for item in value]
    if isinstance(value, str):
        result = value[:MAX_BODY_CHARS]
        for secret in secrets:
            if secret:
                result = result.replace(secret, "[redacted]")
        return result
    if isinstance(value, (bool, float, int)) or value is None:
        return value
    return str(value)[:MAX_BODY_CHARS]
