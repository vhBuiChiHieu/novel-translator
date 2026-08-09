from __future__ import annotations

import json
import logging

import httpx
from pydantic import ValidationError

from novel_translator.config import ModelSettings
from novel_translator.infrastructure.model.exceptions import (
    ModelConnectionError,
    ModelInvalidResponseError,
    ModelProviderError,
    ModelTimeoutError,
)
from novel_translator.infrastructure.model.provider import ProviderMetrics
from novel_translator.schemas.translation_request import TranslationRequest
from novel_translator.schemas.translation_response import TranslationResponse

logger = logging.getLogger(__name__)


class OllamaProvider:
    def __init__(self, settings: ModelSettings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.request_timeout_seconds)
        self.last_metrics = ProviderMetrics()

    def translate(self, request: TranslationRequest) -> TranslationResponse:
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
        for attempt in range(self.settings.max_retries + 1):
            try:
                response = self.client.post(f"{self.settings.base_url.rstrip('/')}/api/chat", json=payload)
                if response.status_code >= 500:
                    raise ModelProviderError(f"Ollama temporary HTTP {response.status_code}")
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
                return parsed
            except httpx.TimeoutException as error:
                failure: ModelProviderError = ModelTimeoutError("Ollama request timed out")
                failure.__cause__ = error
            except httpx.RequestError as error:
                failure = ModelConnectionError("Cannot connect to Ollama")
                failure.__cause__ = error
            except (json.JSONDecodeError, ValidationError, ModelInvalidResponseError) as error:
                failure = ModelInvalidResponseError("Ollama returned invalid structured output")
                failure.__cause__ = error
            except httpx.HTTPStatusError as error:
                raise ModelProviderError(f"Ollama HTTP {error.response.status_code}") from error
            except ModelProviderError as error:
                failure = error
            if attempt == self.settings.max_retries:
                raise failure
            logger.warning("Retrying Ollama request attempt=%s reason=%s", attempt + 1, failure)
        raise AssertionError("unreachable")
