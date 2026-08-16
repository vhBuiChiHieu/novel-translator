from __future__ import annotations

import json
import logging
import time
from typing import cast

import httpx
from pydantic import ValidationError

from novel_translator.config import ModelSettings, ProviderProfile
from novel_translator.infrastructure.model.diagnostics import error_diagnostic, response_diagnostic
from novel_translator.infrastructure.model.exceptions import (
    ModelConnectionError,
    ModelInvalidResponseError,
    ModelProviderError,
    ModelTimeoutError,
)
from novel_translator.infrastructure.model.provider import ProviderAttempt, ProviderDiagnostic, ProviderMetrics
from novel_translator.schemas.translation_request import TranslationRequest
from novel_translator.schemas.translation_response import TranslationResponse

logger = logging.getLogger(__name__)
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"
_GEMINI_SCHEMA_KEYS = {
    "type",
    "format",
    "title",
    "description",
    "nullable",
    "enum",
    "maxItems",
    "minItems",
    "properties",
    "required",
    "propertyOrdering",
    "items",
    "minProperties",
    "maxProperties",
    "anyOf",
}


class GeminiProvider:
    """Google Gemini native generateContent adapter with structured JSON output."""

    def __init__(self, settings: ModelSettings | ProviderProfile, client: httpx.Client | None = None) -> None:
        self.settings = settings
        timeout = int(cast(int | str, self._value("request_timeout_seconds", 300)))
        self.client = client or httpx.Client(timeout=timeout)
        self.last_metrics = ProviderMetrics()
        self.last_diagnostic: ProviderDiagnostic | None = None
        self.last_attempts: list[ProviderAttempt] = []

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        self.last_diagnostic = None
        self.last_metrics = ProviderMetrics()
        self.last_attempts = []
        api_key = getattr(self.settings, "api_key", None)
        if api_key is None:
            message = "Gemini API key is not configured"
            self.last_diagnostic = error_diagnostic("gemini", message)
            self.last_attempts.append(ProviderAttempt(1, "failed", self.last_metrics, self.last_diagnostic))
            logger.error("Gemini request failed before attempt reason=%s", message)
            raise ModelProviderError(message)

        options = getattr(self.settings, "options", None)
        generation_config: dict[str, object] = {
            "responseMimeType": "application/json",
            "responseSchema": self._response_schema(),
        }
        for source, target in (("temperature", "temperature"), ("top_p", "topP"), ("top_k", "topK"), ("max_output_tokens", "maxOutputTokens")):
            value = getattr(options, source, None) if options is not None else None
            if value is not None:
                generation_config[target] = value
        payload: dict[str, object] = {
            "systemInstruction": {"parts": [{"text": request.system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": request.user_prompt}]}],
            "generationConfig": generation_config,
        }
        endpoint = self._endpoint()
        headers = {"x-goog-api-key": api_key.get_secret_value()}
        max_retries = int(cast(int | str, self._value("max_retries", 2)))
        for attempt in range(max_retries + 1):
            started_at = time.perf_counter()
            try:
                response = self.client.post(endpoint, json=payload, headers=headers)
                self.last_diagnostic = response_diagnostic(
                    "gemini", response, "Gemini response received", secrets=(api_key.get_secret_value(),)
                )
                if response.status_code == 429 or response.status_code >= 500:
                    message = f"Gemini temporary HTTP {response.status_code}"
                    self.last_diagnostic = response_diagnostic(
                        "gemini", response, message, secrets=(api_key.get_secret_value(),)
                    )
                    raise ModelProviderError(message)
                response.raise_for_status()
                body = response.json()
                text = self._response_text(body)
                parsed = TranslationResponse.model_validate_json(text)
                usage = body.get("usageMetadata", {})
                self.last_metrics = ProviderMetrics(
                    prompt_tokens=int(usage.get("promptTokenCount", 0)),
                    output_tokens=int(usage.get("candidatesTokenCount", usage.get("outputTokenCount", 0))),
                    duration_ms=int((time.perf_counter() - started_at) * 1000),
                )
                self.last_attempts.append(ProviderAttempt(attempt + 1, "completed", self.last_metrics, self.last_diagnostic))
                return parsed
            except httpx.TimeoutException as error:
                failure: ModelProviderError = ModelTimeoutError("Gemini request timed out")
                failure.__cause__ = error
                self.last_diagnostic = error_diagnostic("gemini", str(failure))
            except httpx.RequestError as error:
                failure = ModelConnectionError("Cannot connect to Gemini")
                failure.__cause__ = error
                self.last_diagnostic = error_diagnostic("gemini", str(failure))
            except (json.JSONDecodeError, ValidationError, ModelInvalidResponseError) as error:
                failure = ModelInvalidResponseError("Gemini returned invalid structured output")
                failure.__cause__ = error
                if self.last_diagnostic is not None:
                    self.last_diagnostic = ProviderDiagnostic(
                        provider="gemini",
                        message=str(failure),
                        status_code=self.last_diagnostic.status_code,
                        body=self.last_diagnostic.body,
                        truncated=self.last_diagnostic.truncated,
                    )
            except httpx.HTTPStatusError as error:
                message = f"Gemini HTTP {error.response.status_code}"
                self.last_diagnostic = response_diagnostic(
                    "gemini", error.response, message, secrets=(api_key.get_secret_value(),)
                )
                logger.error(
                    "Gemini request failed attempt=%s reason=%s raw_response=%s",
                    attempt + 1,
                    message,
                    json.dumps(self.last_diagnostic.body, ensure_ascii=False),
                )
                self.last_attempts.append(ProviderAttempt(attempt + 1, "failed", self.last_metrics, self.last_diagnostic))
                raise ModelProviderError(message) from error
            except ModelProviderError as error:
                failure = error
            self.last_attempts.append(ProviderAttempt(attempt + 1, "failed", self.last_metrics, self.last_diagnostic))
            diagnostic_body = self.last_diagnostic.body if self.last_diagnostic is not None else None
            if attempt == max_retries:
                logger.error(
                    "Gemini request failed after %s attempt(s) reason=%s raw_response=%s",
                    attempt + 1,
                    failure,
                    json.dumps(diagnostic_body, ensure_ascii=False),
                )
                raise failure
            logger.warning(
                "Retrying Gemini request attempt=%s reason=%s raw_response=%s",
                attempt + 1,
                failure,
                json.dumps(diagnostic_body, ensure_ascii=False),
            )
        raise AssertionError("unreachable")

    def _endpoint(self) -> str:
        base_url = str(self._value("base_url", None) or DEFAULT_BASE_URL)
        base = str(base_url).rstrip("/")
        if base.endswith("/v1beta"):
            return f"{base}/models/{self._model()}:generateContent"
        return f"{base}/v1beta/models/{self._model()}:generateContent"

    def _model(self) -> str:
        return str(self._value("model", self._value("name", "gemini-2.5-flash")))

    @staticmethod
    def _response_schema() -> dict[str, object]:
        raw_schema = TranslationResponse.model_json_schema()
        definitions = raw_schema.pop("$defs", {})

        def inline(value: object) -> object:
            if isinstance(value, dict):
                reference = value.get("$ref")
                if isinstance(reference, str):
                    definition_name = reference.rsplit("/", 1)[-1]
                    return inline(definitions[definition_name])
                result: dict[str, object] = {}
                for key, child in value.items():
                    if key not in _GEMINI_SCHEMA_KEYS:
                        continue
                    if key == "type" and isinstance(child, str):
                        result[key] = child.upper()
                    elif key == "properties" and isinstance(child, dict):
                        result[key] = {str(name): inline(schema) for name, schema in child.items()}
                    else:
                        result[key] = inline(child)
                return result
            if isinstance(value, list):
                return [inline(item) for item in value]
            return value

        normalized = inline(raw_schema)
        assert isinstance(normalized, dict)
        return normalized

    def _value(self, name: str, default: object) -> object:
        return getattr(self.settings, name, default)

    @staticmethod
    def _response_text(body: object) -> str:
        if not isinstance(body, dict):
            raise ModelInvalidResponseError("Gemini response is not an object")
        candidates = body.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ModelInvalidResponseError("Gemini response has no candidates")
        content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            raise ModelInvalidResponseError("Gemini response has no candidates[0].content.parts")
        texts = [part["text"] for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str)]
        if not texts:
            raise ModelInvalidResponseError("Gemini response has no text parts")
        return "".join(texts)


__all__ = ["GeminiProvider"]
