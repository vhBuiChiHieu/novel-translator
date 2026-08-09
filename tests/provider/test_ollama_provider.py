import json

import httpx
import pytest

from novel_translator.config import ModelSettings
from novel_translator.infrastructure.model.exceptions import ModelInvalidResponseError, ModelProviderError
from novel_translator.infrastructure.model.ollama_provider import OllamaProvider
from novel_translator.schemas.context_snapshot import ContextSnapshot
from novel_translator.schemas.translation_request import TranslationRequest


def request() -> TranslationRequest:
    return TranslationRequest(
        system_prompt="system",
        user_prompt="user",
        source_text="中文",
        context_snapshot=ContextSnapshot(),
    )


def test_provider_posts_structured_request_and_collects_metrics() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        body = json.loads(http_request.content)
        assert body["model"] == "model"
        assert body["format"]["title"] == "TranslationResponse"
        return httpx.Response(
            200,
            json={
                "message": {"content": '{"translation":"Bản dịch hợp lệ."}'},
                "prompt_eval_count": 7,
                "eval_count": 3,
                "total_duration": 12_000_000,
            },
        )

    provider = OllamaProvider(ModelSettings(name="model"), httpx.Client(transport=httpx.MockTransport(handler)))
    assert provider.translate(request()).translation == "Bản dịch hợp lệ."
    assert provider.last_metrics.prompt_tokens == 7
    assert provider.last_metrics.duration_ms == 12


def test_provider_retries_invalid_structured_response() -> None:
    provider = OllamaProvider(
        ModelSettings(max_retries=0),
        httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"message": {"content": "bad"}}))),
    )
    with pytest.raises(ModelInvalidResponseError):
        provider.translate(request())
    assert provider.last_diagnostic is not None
    assert provider.last_diagnostic.body == {"message": {"content": "bad"}}


def test_provider_captures_error_response_body() -> None:
    provider = OllamaProvider(
        ModelSettings(max_retries=0),
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(400, json={"error": "Invalid request"}))
        ),
    )

    with pytest.raises(ModelProviderError, match="Ollama HTTP 400"):
        provider.translate(request())
    assert provider.last_diagnostic is not None
    assert provider.last_diagnostic.status_code == 400
    assert provider.last_diagnostic.body == {"error": "Invalid request"}
