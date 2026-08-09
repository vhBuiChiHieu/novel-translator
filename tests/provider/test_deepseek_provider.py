import json

import httpx
import pytest
from pydantic import SecretStr

from novel_translator.config import ModelSettings
from novel_translator.infrastructure.model.deepseek_provider import DeepSeekProvider
from novel_translator.infrastructure.model.exceptions import ModelInvalidResponseError, ModelProviderError
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
        assert http_request.url == "https://api.deepseek.com/chat/completions"
        assert http_request.headers["authorization"] == "Bearer token"
        assert body == {
            "model": "deepseek-v4-flash",
            "messages": [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            "stream": False,
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "top_p": 0.9,
        }
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"translation":"Bản dịch hợp lệ."}'}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3},
            },
        )

    settings = ModelSettings(provider="deepseek", name="deepseek-v4-flash", api_key=SecretStr("token"))
    provider = DeepSeekProvider(settings, httpx.Client(transport=httpx.MockTransport(handler)))

    assert provider.translate(request()).translation == "Bản dịch hợp lệ."
    assert provider.last_metrics.prompt_tokens == 7
    assert provider.last_metrics.output_tokens == 3
    assert provider.last_metrics.duration_ms >= 0


def test_provider_retries_invalid_structured_response() -> None:
    settings = ModelSettings(provider="deepseek", api_key=SecretStr("token"), max_retries=0)
    provider = DeepSeekProvider(
        settings,
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"choices": [{"message": {"content": "bad"}}]})
            )
        ),
    )

    with pytest.raises(ModelInvalidResponseError):
        provider.translate(request())


def test_provider_requires_api_key_before_request() -> None:
    provider = DeepSeekProvider(ModelSettings(provider="deepseek"))

    with pytest.raises(ModelProviderError, match="API key"):
        provider.translate(request())


def test_provider_retries_temporary_response() -> None:
    responses = iter(
        [
            httpx.Response(429),
            httpx.Response(200, json={"choices": [{"message": {"content": '{"translation":"ok"}'}}]}),
        ]
    )
    provider = DeepSeekProvider(
        ModelSettings(provider="deepseek", api_key=SecretStr("token"), max_retries=1),
        httpx.Client(transport=httpx.MockTransport(lambda _: next(responses))),
    )

    assert provider.translate(request()).translation == "ok"


def test_provider_does_not_retry_permanent_http_error() -> None:
    provider = DeepSeekProvider(
        ModelSettings(provider="deepseek", api_key=SecretStr("secret-token"), max_retries=1),
        httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(401))),
    )

    with pytest.raises(ModelProviderError, match="DeepSeek HTTP 401") as error:
        provider.translate(request())
    assert "secret-token" not in str(error.value)
