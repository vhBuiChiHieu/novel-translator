from typing import cast

import httpx

from novel_translator.config import ModelSettings, ProviderProfile, ProviderType
from novel_translator.infrastructure.model.deepseek_provider import DeepSeekProvider
from novel_translator.infrastructure.model.gemini_provider import GeminiProvider
from novel_translator.infrastructure.model.ollama_provider import OllamaProvider
from novel_translator.infrastructure.model.provider import ModelProvider

PROVIDER_REGISTRY = {
    ProviderType.OLLAMA: OllamaProvider,
    ProviderType.DEEPSEEK: DeepSeekProvider,
    ProviderType.GEMINI: GeminiProvider,
}


def create_model_provider(
    settings: ModelSettings | ProviderProfile,
    client: httpx.Client | None = None,
) -> ModelProvider:
    provider_name = settings.provider.value if isinstance(settings.provider, ProviderType) else settings.provider.lower()
    provider_type = ProviderType(provider_name) if provider_name in {item.value for item in ProviderType} else None
    provider_class = PROVIDER_REGISTRY.get(provider_type) if provider_type is not None else None
    if provider_class is None:
        raise ValueError(f"Unsupported model provider: {settings.provider}")
    return cast(ModelProvider, provider_class(settings, client))
