from __future__ import annotations

from typing import Any

from .enums import ProviderType

# Keep this list limited to text-generation models suitable for chapter translation.
# It is intentionally versioned in source rather than fetched at runtime so the
# Settings screen remains deterministic and does not need provider credentials.
_MODEL_OPTIONS: dict[ProviderType, tuple[dict[str, str], ...]] = {
    ProviderType.DEEPSEEK: (
        {"id": "deepseek-v4-flash", "label": "DeepSeek V4 Flash", "status": "stable"},
        {"id": "deepseek-v4-pro", "label": "DeepSeek V4 Pro", "status": "stable"},
    ),
    ProviderType.GEMINI: (
        {"id": "gemini-3.7-flash", "label": "Gemini 3.7 Flash", "status": "stable"},
        {"id": "gemini-3.6-flash", "label": "Gemini 3.6 Flash", "status": "stable"},
        {"id": "gemini-3.5-flash", "label": "Gemini 3.5 Flash", "status": "stable"},
        {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash-Lite", "status": "stable"},
        {"id": "gemini-3.1-flash-lite", "label": "Gemini 3.1 Flash-Lite", "status": "stable"},
        {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro", "status": "preview"},
        {"id": "gemini-3-flash-preview", "label": "Gemini 3 Flash", "status": "preview"},
        {"id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro", "status": "stable"},
        {"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash", "status": "stable"},
        {"id": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash-Lite", "status": "stable"},
    ),
}


def model_options_for(provider: ProviderType | str) -> list[dict[str, str]]:
    """Return selectable text-model metadata for a provider.

    Ollama deliberately returns no presets because its available models are
    installed locally and can differ from machine to machine.
    """

    try:
        provider_type = ProviderType(provider)
    except ValueError:
        return []
    return [dict(option) for option in _MODEL_OPTIONS.get(provider_type, ())]


def model_catalog() -> dict[str, list[dict[str, Any]]]:
    """Return JSON-friendly model presets for provider-aware clients."""

    return {provider.value: model_options_for(provider) for provider in ProviderType}


__all__ = ["model_catalog", "model_options_for"]
