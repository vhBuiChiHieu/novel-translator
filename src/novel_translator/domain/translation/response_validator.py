from novel_translator.config import ValidationSettings
from novel_translator.schemas.translation_response import TranslationResponse


class ResponseValidationError(ValueError):
    pass


def validate_response(
    response: TranslationResponse, source_text: str, settings: ValidationSettings
) -> TranslationResponse:
    translation = response.translation.strip()
    if not translation:
        raise ResponseValidationError("Translation is empty")
    if translation == source_text.strip():
        raise ResponseValidationError("Translation is identical to source")
    ratio = len(translation) / max(len(source_text), 1)
    if not settings.min_length_ratio <= ratio <= settings.max_length_ratio:
        raise ResponseValidationError(f"Translation length ratio {ratio:.2f} is outside configured bounds")
    if len(response.context_updates) > settings.max_context_updates:
        raise ResponseValidationError("Response has too many context updates")
    return response
