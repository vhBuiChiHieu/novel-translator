from dataclasses import dataclass
from typing import Protocol

from novel_translator.schemas.translation_request import TranslationRequest
from novel_translator.schemas.translation_response import TranslationResponse


@dataclass(frozen=True)
class ProviderMetrics:
    prompt_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0


@dataclass(frozen=True)
class ProviderDiagnostic:
    provider: str
    message: str
    status_code: int | None = None
    body: object | None = None
    truncated: bool = False

    def model_dump(self) -> dict[str, object | None]:
        return {
            "provider": self.provider,
            "message": self.message,
            "status_code": self.status_code,
            "body": self.body,
            "truncated": self.truncated,
        }


class ModelProvider(Protocol):
    last_metrics: ProviderMetrics
    last_diagnostic: ProviderDiagnostic | None

    def translate(self, request: TranslationRequest) -> TranslationResponse:
        """Translate a normalized request without touching persistence."""
