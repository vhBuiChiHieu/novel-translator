from pydantic import BaseModel, Field

from novel_translator.schemas.context_update import ContextUpdate


class TranslationResponse(BaseModel):
    translation: str = Field(min_length=1)
    context_updates: list[ContextUpdate] = Field(default_factory=list)
