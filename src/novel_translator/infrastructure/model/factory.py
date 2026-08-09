import httpx

from novel_translator.config import ModelSettings
from novel_translator.infrastructure.model.deepseek_provider import DeepSeekProvider
from novel_translator.infrastructure.model.ollama_provider import OllamaProvider
from novel_translator.infrastructure.model.provider import ModelProvider


def create_model_provider(settings: ModelSettings, client: httpx.Client | None = None) -> ModelProvider:
    provider = settings.provider.lower()
    if provider == "ollama":
        return OllamaProvider(settings, client)
    if provider == "deepseek":
        return DeepSeekProvider(settings, client)
    raise ValueError(f"Unsupported model provider: {settings.provider}")
