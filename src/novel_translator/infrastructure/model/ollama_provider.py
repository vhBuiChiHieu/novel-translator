from __future__ import annotations

import json
import logging

import httpx
from pydantic import ValidationError

from novel_translator.config import ModelSettings
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


class OllamaProvider:
    def __init__(self, settings: ModelSettings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.request_timeout_seconds)
        self.last_metrics = ProviderMetrics()
        self.last_diagnostic: ProviderDiagnostic | None = None
        self.last_attempts: list[ProviderAttempt] = []

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        self.last_diagnostic = None
        self.last_metrics = ProviderMetrics()
        self.last_attempts = []
        payload = {
            "model": self.settings.name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "format": TranslationResponse.model_json_schema(),
            "stream": False,
            "think": self.settings.options.think,
            "options": self.settings.options.model_dump(exclude={"think"}),
        }
        endpoint = f"{self.settings.base_url.rstrip('/')}/api/chat"
        for attempt in range(self.settings.max_retries + 1):
            try:
                response = self.client.post(endpoint, json=payload)
                self.last_diagnostic = response_diagnostic("ollama", response, "Ollama response received")
                if response.status_code >= 500:
                    message = f"Ollama temporary HTTP {response.status_code}"
                    self.last_diagnostic = response_diagnostic("ollama", response, message)
                    raise ModelProviderError(message)
                response.raise_for_status()
                body = response.json()
                content = body.get("message", {}).get("content")
                if not isinstance(content, str):
                    raise ModelInvalidResponseError("Ollama response has no message.content")
                parsed = TranslationResponse.model_validate_json(content)
                self.last_metrics = ProviderMetrics(
                    prompt_tokens=int(body.get("prompt_eval_count", 0)),
                    output_tokens=int(body.get("eval_count", 0)),
                    duration_ms=int(body.get("total_duration", 0) / 1_000_000),
                )
                self.last_attempts.append(
                    ProviderAttempt(attempt + 1, "completed", self.last_metrics, self.last_diagnostic)
                )
                return parsed
            except httpx.TimeoutException as error:
                failure: ModelProviderError = ModelTimeoutError("Ollama request timed out")
                failure.__cause__ = error
                self.last_diagnostic = error_diagnostic("ollama", str(failure))
            except httpx.RequestError as error:
                failure = ModelConnectionError("Cannot connect to Ollama")
                failure.__cause__ = error
                self.last_diagnostic = error_diagnostic("ollama", str(failure))
            except (json.JSONDecodeError, ValidationError, ModelInvalidResponseError) as error:
                failure = ModelInvalidResponseError("Ollama returned invalid structured output")
                failure.__cause__ = error
                if self.last_diagnostic is not None:
                    self.last_diagnostic = ProviderDiagnostic(
                        provider="ollama",
                        message=str(failure),
                        status_code=self.last_diagnostic.status_code,
                        body=self.last_diagnostic.body,
                        truncated=self.last_diagnostic.truncated,
                    )
            except httpx.HTTPStatusError as error:
                message = f"Ollama HTTP {error.response.status_code}"
                self.last_diagnostic = response_diagnostic("ollama", error.response, message)
                logger.error(
                    "Ollama request failed attempt=%s reason=%s raw_response=%s",
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
            if attempt == self.settings.max_retries:
                logger.error(
                    "Ollama request failed after %s attempt(s) reason=%s raw_response=%s",
                    attempt + 1,
                    failure,
                    json.dumps(diagnostic_body, ensure_ascii=False),
                )
                raise failure
            logger.warning(
                "Retrying Ollama request attempt=%s reason=%s raw_response=%s",
                attempt + 1,
                failure,
                json.dumps(diagnostic_body, ensure_ascii=False),
            )
        raise AssertionError("unreachable")
