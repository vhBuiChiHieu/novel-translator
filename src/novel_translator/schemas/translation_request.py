from pydantic import BaseModel, Field

from novel_translator.schemas.context_snapshot import ContextSnapshot


class TranslationRequest(BaseModel):
    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
    source_text: str = Field(min_length=1)
    context_snapshot: ContextSnapshot
