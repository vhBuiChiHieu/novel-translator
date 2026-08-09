import httpx
import pytest
from pydantic import SecretStr

from novel_translator.config import ModelSettings
from novel_translator.infrastructure.model.deepseek_provider import DeepSeekProvider
from novel_translator.infrastructure.model.factory import create_model_provider
from novel_translator.infrastructure.model.ollama_provider import OllamaProvider


def test_factory_selects_ollama_provider() -> None:
    provider = create_model_provider(ModelSettings(), httpx.Client())

    assert isinstance(provider, OllamaProvider)


def test_factory_selects_deepseek_provider() -> None:
    provider = create_model_provider(
        ModelSettings(provider="DeepSeek", api_key=SecretStr("token")), httpx.Client()
    )

    assert isinstance(provider, DeepSeekProvider)


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported model provider: unknown"):
        create_model_provider(ModelSettings(provider="unknown"))
