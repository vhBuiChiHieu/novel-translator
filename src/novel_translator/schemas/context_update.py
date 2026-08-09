from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from novel_translator.domain.model.enums import ContextType


class ContextUpdate(BaseModel):
    """A model-proposed durable context record before it reaches persistence."""

    type: ContextType
    source: str | None = None
    translation: str | None = None
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    speaker: str | None = None
    listener: str | None = None
    speaker_pronoun: str | None = None
    listener_pronoun: str | None = None
    source_title: str | None = None
    translated_title: str | None = None
    fact_key: str | None = None
    fact_value: str | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> ContextUpdate:
        if self.type in {
            ContextType.CHARACTER,
            ContextType.TERM,
            ContextType.LOCATION,
            ContextType.ORGANIZATION,
        } and not self.source:
            raise ValueError("source is required for mapping context")
        if self.type == ContextType.RELATIONSHIP and not (
            self.subject and self.predicate and self.object
        ):
            raise ValueError("relationship requires subject, predicate, and object")
        if self.type == ContextType.WORLD_FACT and not (self.subject and self.fact_key and self.fact_value):
            raise ValueError("world_fact requires subject, fact_key, and fact_value")
        return self
