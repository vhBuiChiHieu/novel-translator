import json

import httpx
import pytest
from pydantic import SecretStr

from novel_translator.config import ModelSettings, ProviderProfile, ProviderType
from novel_translator.infrastructure.model.exceptions import ModelInvalidResponseError, ModelProviderError
from novel_translator.infrastructure.model.gemini_provider import GeminiProvider
from novel_translator.schemas.context_snapshot import ContextSnapshot
from novel_translator.schemas.translation_request import TranslationRequest


def request() -> TranslationRequest:
    return TranslationRequest(
        system_prompt="system",
        user_prompt="user",
        source_text="中文",
        context_snapshot=ContextSnapshot(),
    )


def test_gemini_maps_native_structured_request_and_usage() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        body = json.loads(http_request.content)
        assert str(http_request.url) == (
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        )
        assert http_request.headers["x-goog-api-key"] == "secret-token"
        assert body["systemInstruction"] == {"parts": [{"text": "system"}]}
        assert body["contents"] == [{"role": "user", "parts": [{"text": "user"}]}]
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert body["generationConfig"]["responseSchema"]["title"] == "TranslationResponse"
        schema_text = json.dumps(body["generationConfig"]["responseSchema"])
        assert "$defs" not in schema_text
        assert "$ref" not in schema_text
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": '{"translation":"Bản dịch"}'}]}}],
                "usageMetadata": {"promptTokenCount": 8, "candidatesTokenCount": 4},
            },
        )

    profile = ProviderProfile(
        provider=ProviderType.GEMINI,
        model="gemini-2.5-flash",
        api_key=SecretStr("secret-token"),
        options={"temperature": 0.2, "top_p": 0.9, "top_k": 20, "max_output_tokens": 500},
    )
    provider = GeminiProvider(profile, httpx.Client(transport=httpx.MockTransport(handler)))

    assert provider.translate(request()).translation == "Bản dịch"
    assert provider.last_metrics.prompt_tokens == 8
    assert provider.last_metrics.output_tokens == 4


def test_gemini_concatenates_multiple_text_parts() -> None:
    provider = GeminiProvider(
        ModelSettings(provider="gemini", api_key=SecretStr("token"), name="model", max_retries=0),
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    json={"candidates": [{"content": {"parts": [{"text": '{"translation":"A'}, {"text": 'B"}'}]}}]},
                )
            )
        ),
    )

    assert provider.translate(request()).translation == "AB"


def test_gemini_retries_rate_limit_and_redacts_credential() -> None:
    responses = iter(
        [
            httpx.Response(429, json={"error": {"message": "secret-token"}}),
            httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"translation":"ok"}'}]}}]}),
        ]
    )
    provider = GeminiProvider(
        ModelSettings(provider="gemini", api_key=SecretStr("secret-token"), max_retries=1),
        httpx.Client(transport=httpx.MockTransport(lambda _: next(responses))),
    )

    assert provider.translate(request()).translation == "ok"


def test_gemini_rejects_missing_text() -> None:
    provider = GeminiProvider(
        ModelSettings(provider="gemini", api_key=SecretStr("token"), max_retries=0),
        httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"candidates": [{}]}))),
    )

    with pytest.raises(ModelInvalidResponseError):
        provider.translate(request())


def test_gemini_requires_credential() -> None:
    provider = GeminiProvider(ModelSettings(provider="gemini", max_retries=0))

    with pytest.raises(ModelProviderError, match="API key"):
        provider.translate(request())
