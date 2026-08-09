from typing import Protocol

from novel_translator.schemas.translation_request import TranslationRequest
from novel_translator.schemas.translation_response import TranslationResponse


class ModelProvider(Protocol):
    def translate(self, request: TranslationRequest) -> TranslationResponse:
        """Translate a normalized request without touching persistence."""
