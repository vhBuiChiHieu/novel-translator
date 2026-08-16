from __future__ import annotations

import json
import logging
import time

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
DEFAULT_BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider:
    def __init__(self, settings: ModelSettings | ProviderProfile, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.Client(timeout=getattr(settings, "request_timeout_seconds", 300))
        self.last_metrics = ProviderMetrics()
        self.last_diagnostic: ProviderDiagnostic | None = None
        self.last_attempts: list[ProviderAttempt] = []

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        self.last_diagnostic = None
        self.last_metrics = ProviderMetrics()
        self.last_attempts = []
        if self.settings.api_key is None:
            message = "DeepSeek API key is not configured"
            self.last_diagnostic = error_diagnostic("deepseek", message)
            self.last_attempts.append(ProviderAttempt(1, "failed", self.last_metrics, self.last_diagnostic))
            logger.error("DeepSeek request failed before attempt reason=%s", message)
            raise ModelProviderError(message)
        payload: dict[str, object] = {
            "model": getattr(self.settings, "name", None) or getattr(self.settings, "model"),
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        if self.settings.options.temperature is not None:
            payload["temperature"] = self.settings.options.temperature
        if self.settings.options.top_p is not None:
            payload["top_p"] = self.settings.options.top_p
        if self.settings.options.max_output_tokens is not None:
            payload["max_tokens"] = self.settings.options.max_output_tokens
        headers = {"Authorization": f"Bearer {self.settings.api_key.get_secret_value()}"}
        endpoint = f"{self._base_url.rstrip('/')}/chat/completions"
        for attempt in range(getattr(self.settings, "max_retries", 2) + 1):
            started_at = time.perf_counter()
            try:
                response = self.client.post(endpoint, json=payload, headers=headers)
                self.last_diagnostic = response_diagnostic(
                    "deepseek", response, "DeepSeek response received", secrets=(self.settings.api_key.get_secret_value(),)
                )
                if response.status_code == 429 or response.status_code >= 500:
                    message = f"DeepSeek temporary HTTP {response.status_code}"
                    self.last_diagnostic = response_diagnostic(
                        "deepseek", response, message, secrets=(self.settings.api_key.get_secret_value(),)
                    )
                    raise ModelProviderError(message)
                response.raise_for_status()
                body = response.json()
                choices = body.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise ModelInvalidResponseError("DeepSeek response has no choices")
                content = choices[0].get("message", {}).get("content")
                if not isinstance(content, str):
                    raise ModelInvalidResponseError("DeepSeek response has no choices[0].message.content")
                parsed = TranslationResponse.model_validate_json(content)
                usage = body.get("usage", {})
                self.last_metrics = ProviderMetrics(
                    prompt_tokens=int(usage.get("prompt_tokens", 0)),
                    output_tokens=int(usage.get("completion_tokens", 0)),
                    duration_ms=int((time.perf_counter() - started_at) * 1000),
                )
                self.last_attempts.append(
                    ProviderAttempt(attempt + 1, "completed", self.last_metrics, self.last_diagnostic)
                )
                return parsed
            except httpx.TimeoutException as error:
                failure: ModelProviderError = ModelTimeoutError("DeepSeek request timed out")
                failure.__cause__ = error
                self.last_diagnostic = error_diagnostic("deepseek", str(failure))
            except httpx.RequestError as error:
                failure = ModelConnectionError("Cannot connect to DeepSeek")
                failure.__cause__ = error
                self.last_diagnostic = error_diagnostic("deepseek", str(failure))
            except (json.JSONDecodeError, ValidationError, ModelInvalidResponseError) as error:
                failure = ModelInvalidResponseError("DeepSeek returned invalid structured output")
                failure.__cause__ = error
                if self.last_diagnostic is not None:
                    self.last_diagnostic = ProviderDiagnostic(
                        provider="deepseek",
                        message=str(failure),
                        status_code=self.last_diagnostic.status_code,
                        body=self.last_diagnostic.body,
                        truncated=self.last_diagnostic.truncated,
                    )
            except httpx.HTTPStatusError as error:
                message = f"DeepSeek HTTP {error.response.status_code}"
                self.last_diagnostic = response_diagnostic(
                    "deepseek", error.response, message, secrets=(self.settings.api_key.get_secret_value(),)
                )
                logger.error(
                    "DeepSeek request failed attempt=%s reason=%s raw_response=%s",
                    attempt + 1,
                    message,
                    json.dumps(self.last_diagnostic.body, ensure_ascii=False),
                )
                self.last_attempts.append(
                    ProviderAttempt(attempt + 1, "failed", self.last_metrics, self.last_diagnostic)
                )
                raise ModelProviderError(message) from error
            except ModelProviderError as error:
                failure = error
            self.last_attempts.append(
                ProviderAttempt(attempt + 1, "failed", self.last_metrics, self.last_diagnostic)
            )
            diagnostic_body = self.last_diagnostic.body if self.last_diagnostic is not None else None
            if attempt == getattr(self.settings, "max_retries", 2):
                logger.error(
                    "DeepSeek request failed after %s attempt(s) reason=%s raw_response=%s",
                    attempt + 1,
                    failure,
                    json.dumps(diagnostic_body, ensure_ascii=False),
                )
                raise failure
            logger.warning(
                "Retrying DeepSeek request attempt=%s reason=%s raw_response=%s",
                attempt + 1,
                failure,
                json.dumps(diagnostic_body, ensure_ascii=False),
            )
        raise AssertionError("unreachable")

    @property
    def _base_url(self) -> str:
        provider = getattr(self.settings, "provider", "deepseek")
        provider_name = provider.value if hasattr(provider, "value") else str(provider).lower()
        base_url = getattr(self.settings, "base_url", None)
        if provider_name == "deepseek" and base_url == "http://localhost:11434":
            return DEFAULT_BASE_URL
        return base_url or DEFAULT_BASE_URL
