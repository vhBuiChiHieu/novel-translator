from __future__ import annotations

import json
import logging
import time

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
DEFAULT_BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider:
    def __init__(self, settings: ModelSettings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.request_timeout_seconds)
        self.last_metrics = ProviderMetrics()

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        if self.settings.api_key is None:
            raise ModelProviderError("DeepSeek API key is not configured")
        payload = {
            "model": self.settings.name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "stream": False,
            "response_format": {"type": "json_object"},
            "temperature": self.settings.options.temperature,
            "top_p": self.settings.options.top_p,
        }
        headers = {"Authorization": f"Bearer {self.settings.api_key.get_secret_value()}"}
        endpoint = f"{self._base_url.rstrip('/')}/chat/completions"
        for attempt in range(self.settings.max_retries + 1):
            started_at = time.perf_counter()
            try:
                response = self.client.post(endpoint, json=payload, headers=headers)
                if response.status_code == 429 or response.status_code >= 500:
                    raise ModelProviderError(f"DeepSeek temporary HTTP {response.status_code}")
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
                return parsed
            except httpx.TimeoutException as error:
                failure: ModelProviderError = ModelTimeoutError("DeepSeek request timed out")
                failure.__cause__ = error
            except httpx.RequestError as error:
                failure = ModelConnectionError("Cannot connect to DeepSeek")
                failure.__cause__ = error
            except (json.JSONDecodeError, ValidationError, ModelInvalidResponseError) as error:
                failure = ModelInvalidResponseError("DeepSeek returned invalid structured output")
                failure.__cause__ = error
            except httpx.HTTPStatusError as error:
                raise ModelProviderError(f"DeepSeek HTTP {error.response.status_code}") from error
            except ModelProviderError as error:
                failure = error
            if attempt == self.settings.max_retries:
                raise failure
            logger.warning("Retrying DeepSeek request attempt=%s reason=%s", attempt + 1, failure)
        raise AssertionError("unreachable")

    @property
    def _base_url(self) -> str:
        if self.settings.provider.lower() == "deepseek" and self.settings.base_url == "http://localhost:11434":
            return DEFAULT_BASE_URL
        return self.settings.base_url or DEFAULT_BASE_URL
