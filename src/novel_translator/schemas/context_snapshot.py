from pydantic import BaseModel, Field


class ContextItem(BaseModel):
    source: str
    translation: str | None = None
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)


class RelationshipContext(BaseModel):
    subject: str
    predicate: str
    object: str
    description: str | None = None


class AddressingContext(BaseModel):
    speaker: str | None = None
    listener: str | None = None
    speaker_pronoun: str | None = None
    listener_pronoun: str | None = None
    source_title: str | None = None
    translated_title: str | None = None


class WorldFactContext(BaseModel):
    subject: str
    fact_key: str
    fact_value: str
    description: str | None = None


class ContextSnapshot(BaseModel):
    characters: list[ContextItem] = Field(default_factory=list)
    terms: list[ContextItem] = Field(default_factory=list)
    locations: list[ContextItem] = Field(default_factory=list)
    organizations: list[ContextItem] = Field(default_factory=list)
    relationships: list[RelationshipContext] = Field(default_factory=list)
    addressing_rules: list[AddressingContext] = Field(default_factory=list)
    world_facts: list[WorldFactContext] = Field(default_factory=list)
