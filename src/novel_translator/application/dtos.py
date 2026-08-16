from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class NovelDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_name: str
    title: str
    source_language: str
    target_language: str


class ChapterDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_number: int
    source_path: str
    translated_path: str | None = None
    source_hash: str
    status: str
    source_text: str | None = None


class TranslationJobDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    chapter_number: int | None = None
    model_provider: str
    model_name: str
    profile_id: str | None = None
    config_hash: str | None = None
    prompt_version: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_prompt_tokens: int
    total_output_tokens: int
    total_duration_ms: int


class TranslationChunkDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    translation_job_id: int
    chapter_id: int
    chunk_index: int
    source_text: str
    translated_text: str | None = None
    previous_translation_tail: str
    context_snapshot_json: dict[str, object] | None = None
    raw_model_response_json: dict[str, object] | None = None
    prompt_hash: str | None = None
    status: str
    error_message: str | None = None
    prompt_tokens: int
    output_tokens: int
    duration_ms: int


class ModelCallDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    translation_job_id: int
    translation_chunk_id: int
    attempt_number: int
    provider: str
    model_name: str
    prompt_version: str
    system_prompt: str
    user_prompt: str
    source_text: str
    context_snapshot_json: dict[str, object] | None = None
    previous_translation_tail: str
    response_json: dict[str, object] | None = None
    translated_text: str | None = None
    diagnostic_json: dict[str, object] | None = None
    prompt_hash: str
    prompt_tokens: int
    output_tokens: int
    duration_ms: int
    status: str
    created_at: datetime


class ContextItemDTO(BaseModel):
    id: int
    context_type: str
    source: str
    translation: str | None = None
    description: str | None = None
    status: str


class DatabaseTableDTO(BaseModel):
    """A read-only, display-friendly view of one project database table."""

    name: str
    columns: list[str]
    rows: list[dict[str, str]]


class ConflictDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    context_type: str
    source_key: str
    existing_value: str | None = None
    candidate_value: str | None = None
    chapter_id: int | None = None
    chunk_id: int | None = None
    status: str
    created_at: datetime
    resolved_at: datetime | None = None


class DashboardDTO(BaseModel):
    project: NovelDTO
    project_path: Path
    provider: str
    model: str
    chapter_counts: dict[str, int]
    running_jobs: list[TranslationJobDTO]
    open_conflicts: int
    health_ok: bool = True
    health_errors: list[str] = Field(default_factory=list)


class ChapterPreviewDTO(BaseModel):
    chapter_number: int
    path: Path
    valid_utf8: bool
    source_text: str | None = None
    error: str | None = None
