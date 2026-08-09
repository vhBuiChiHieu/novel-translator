from novel_translator.config import ContextSettings
from novel_translator.domain.model.enums import ContextType
from novel_translator.schemas.context_update import ContextUpdate


def should_auto_confirm(update: ContextUpdate, source_text: str, settings: ContextSettings) -> bool:
    enabled = getattr(settings.auto_confirm, update.type.value)
    if not enabled or update.confidence < settings.minimum_confidence:
        return False
    if update.type in {
        ContextType.CHARACTER,
        ContextType.TERM,
        ContextType.LOCATION,
        ContextType.ORGANIZATION,
    }:
        return bool(update.source and update.source in source_text)
    return True
