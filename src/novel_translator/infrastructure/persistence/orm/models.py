from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from novel_translator.infrastructure.persistence.orm.base import Base, TimestampMixin


class NovelORM(TimestampMixin, Base):
    __tablename__ = "novel"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_name: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    source_language: Mapped[str] = mapped_column(String(8), default="zh")
    target_language: Mapped[str] = mapped_column(String(8), default="vi")


class ChapterORM(TimestampMixin, Base):
    __tablename__ = "chapter"
    __table_args__ = (UniqueConstraint("novel_id", "chapter_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novel.id"), index=True)
    chapter_number: Mapped[int] = mapped_column(Integer)
    source_path: Mapped[str] = mapped_column(String(1024))
    translated_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="imported", index=True)


class EntityORM(TimestampMixin, Base):
    __tablename__ = "entity"
    __table_args__ = (UniqueConstraint("novel_id", "entity_type", "source_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novel.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    source_name: Mapped[str] = mapped_column(String(512), index=True)
    translated_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    first_seen_chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapter.id"), nullable=True)
    first_seen_chunk_id: Mapped[int | None] = mapped_column(ForeignKey("translation_chunk.id"), nullable=True)
    created_by_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(128), nullable=True)


class EntityAliasORM(Base):
    __tablename__ = "entity_alias"
    __table_args__ = (UniqueConstraint("entity_id", "alias"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entity.id"), index=True)
    alias: Mapped[str] = mapped_column(String(512))
    alias_type: Mapped[str] = mapped_column(String(32), default="source_alias")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class TerminologyORM(TimestampMixin, Base):
    __tablename__ = "terminology"
    __table_args__ = (UniqueConstraint("novel_id", "source_term"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novel.id"), index=True)
    source_term: Mapped[str] = mapped_column(String(512), index=True)
    translated_term: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    first_seen_chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapter.id"), nullable=True)
    first_seen_chunk_id: Mapped[int | None] = mapped_column(ForeignKey("translation_chunk.id"), nullable=True)
    created_by_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(128), nullable=True)


class RelationshipORM(TimestampMixin, Base):
    __tablename__ = "relationship"
    __table_args__ = (UniqueConstraint("novel_id", "subject_entity_id", "predicate", "object_entity_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novel.id"), index=True)
    subject_entity_id: Mapped[int] = mapped_column(ForeignKey("entity.id"))
    predicate: Mapped[str] = mapped_column(String(128))
    object_entity_id: Mapped[int] = mapped_column(ForeignKey("entity.id"))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    first_seen_chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapter.id"), nullable=True)
    first_seen_chunk_id: Mapped[int | None] = mapped_column(ForeignKey("translation_chunk.id"), nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.0)


class AddressingRuleORM(TimestampMixin, Base):
    __tablename__ = "addressing_rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novel.id"), index=True)
    speaker_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entity.id"), nullable=True)
    listener_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entity.id"), nullable=True)
    speaker_pronoun: Mapped[str | None] = mapped_column(String(128), nullable=True)
    listener_pronoun: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    translated_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    first_seen_chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapter.id"), nullable=True)
    first_seen_chunk_id: Mapped[int | None] = mapped_column(ForeignKey("translation_chunk.id"), nullable=True)


class ContextFactORM(TimestampMixin, Base):
    __tablename__ = "context_fact"
    __table_args__ = (UniqueConstraint("novel_id", "subject", "fact_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novel.id"), index=True)
    subject: Mapped[str] = mapped_column(String(512))
    fact_key: Mapped[str] = mapped_column(String(512))
    fact_value: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    first_seen_chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapter.id"), nullable=True)
    first_seen_chunk_id: Mapped[int | None] = mapped_column(ForeignKey("translation_chunk.id"), nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.0)


class TranslationJobORM(TimestampMixin, Base):
    __tablename__ = "translation_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novel.id"), index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapter.id"), index=True)
    model_provider: Mapped[str] = mapped_column(String(64))
    model_name: Mapped[str] = mapped_column(String(255))
    profile_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    total_prompt_tokens: Mapped[int] = mapped_column(default=0)
    total_output_tokens: Mapped[int] = mapped_column(default=0)
    total_duration_ms: Mapped[int] = mapped_column(default=0)


class TranslationChunkORM(TimestampMixin, Base):
    __tablename__ = "translation_chunk"
    __table_args__ = (UniqueConstraint("translation_job_id", "chunk_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    translation_job_id: Mapped[int] = mapped_column(ForeignKey("translation_job.id"), index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapter.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    source_text: Mapped[str] = mapped_column(Text)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_translation_tail: Mapped[str] = mapped_column(Text, default="")
    context_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw_model_response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    duration_ms: Mapped[int] = mapped_column(default=0)


class ModelCallORM(Base):
    """Immutable-enough audit record for each provider invocation."""

    __tablename__ = "model_call"
    __table_args__ = (Index("ix_model_call_chunk", "translation_chunk_id", "attempt_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    translation_job_id: Mapped[int] = mapped_column(ForeignKey("translation_job.id"), index=True)
    translation_chunk_id: Mapped[int] = mapped_column(ForeignKey("translation_chunk.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(64))
    model_name: Mapped[str] = mapped_column(String(255))
    prompt_version: Mapped[str] = mapped_column(String(128))
    system_prompt: Mapped[str] = mapped_column(Text)
    user_prompt: Mapped[str] = mapped_column(Text)
    source_text: Mapped[str] = mapped_column(Text)
    context_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    previous_translation_tail: Mapped[str] = mapped_column(Text, default="")
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnostic_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    prompt_hash: Mapped[str] = mapped_column(String(64))
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    duration_ms: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ContextConflictORM(Base):
    __tablename__ = "context_conflict"
    __table_args__ = (Index("ix_conflict_novel_status", "novel_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    novel_id: Mapped[int] = mapped_column(ForeignKey("novel.id"), index=True)
    context_type: Mapped[str] = mapped_column(String(32))
    source_key: Mapped[str] = mapped_column(String(512))
    existing_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey("chapter.id"), nullable=True)
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("translation_chunk.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
