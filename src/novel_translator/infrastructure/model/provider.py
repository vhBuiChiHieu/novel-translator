from dataclasses import dataclass
from typing import Protocol

from novel_translator.schemas.translation_request import TranslationRequest
from novel_translator.schemas.translation_response import TranslationResponse


@dataclass(frozen=True)
class ProviderMetrics:
    prompt_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0


class ModelProvider(Protocol):
    last_metrics: ProviderMetrics

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        """Translate a normalized request without touching persistence."""
