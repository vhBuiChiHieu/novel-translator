"""Initial V0.1 schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table("novel", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("project_name", sa.String(255), unique=True, nullable=False), sa.Column("title", sa.String(512), nullable=False, server_default=""), sa.Column("source_language", sa.String(8), nullable=False), sa.Column("target_language", sa.String(8), nullable=False), *_timestamps())
    op.create_table("chapter", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novel.id"), nullable=False), sa.Column("chapter_number", sa.Integer(), nullable=False), sa.Column("source_path", sa.String(1024), nullable=False), sa.Column("translated_path", sa.String(1024)), sa.Column("source_hash", sa.String(64), nullable=False), sa.Column("status", sa.String(32), nullable=False), *_timestamps(), sa.UniqueConstraint("novel_id", "chapter_number"))
    op.create_index("ix_chapter_novel", "chapter", ["novel_id"])
    op.create_table("translation_job", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novel.id"), nullable=False), sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapter.id"), nullable=False), sa.Column("model_provider", sa.String(64), nullable=False), sa.Column("model_name", sa.String(255), nullable=False), sa.Column("prompt_version", sa.String(128), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("started_at", sa.DateTime()), sa.Column("finished_at", sa.DateTime()), sa.Column("total_prompt_tokens", sa.Integer(), nullable=False, server_default="0"), sa.Column("total_output_tokens", sa.Integer(), nullable=False, server_default="0"), sa.Column("total_duration_ms", sa.Integer(), nullable=False, server_default="0"), *_timestamps())
    op.create_index("ix_job_chapter", "translation_job", ["chapter_id"])
    op.create_table("translation_chunk", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("translation_job_id", sa.Integer(), sa.ForeignKey("translation_job.id"), nullable=False), sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapter.id"), nullable=False), sa.Column("chunk_index", sa.Integer(), nullable=False), sa.Column("source_text", sa.Text(), nullable=False), sa.Column("translated_text", sa.Text()), sa.Column("previous_translation_tail", sa.Text(), nullable=False, server_default=""), sa.Column("context_snapshot_json", sa.JSON()), sa.Column("raw_model_response_json", sa.JSON()), sa.Column("prompt_hash", sa.String(64)), sa.Column("status", sa.String(32), nullable=False), sa.Column("error_message", sa.Text()), sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"), sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"), sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"), *_timestamps(), sa.UniqueConstraint("translation_job_id", "chunk_index"))
    op.create_table("entity", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novel.id"), nullable=False), sa.Column("entity_type", sa.String(32), nullable=False), sa.Column("source_name", sa.String(512), nullable=False), sa.Column("translated_name", sa.String(512)), sa.Column("description", sa.Text()), sa.Column("status", sa.String(32), nullable=False), sa.Column("first_seen_chapter_id", sa.Integer(), sa.ForeignKey("chapter.id")), sa.Column("first_seen_chunk_id", sa.Integer(), sa.ForeignKey("translation_chunk.id")), sa.Column("created_by_model", sa.String(255)), sa.Column("prompt_version", sa.String(128)), *_timestamps(), sa.UniqueConstraint("novel_id", "entity_type", "source_name"))
    op.create_index("ix_entity_match", "entity", ["novel_id", "status", "source_name"])
    op.create_table("entity_alias", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("entity_id", sa.Integer(), sa.ForeignKey("entity.id"), nullable=False), sa.Column("alias", sa.String(512), nullable=False), sa.Column("alias_type", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("entity_id", "alias"))
    op.create_table("terminology", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novel.id"), nullable=False), sa.Column("source_term", sa.String(512), nullable=False), sa.Column("translated_term", sa.String(512)), sa.Column("description", sa.Text()), sa.Column("status", sa.String(32), nullable=False), sa.Column("first_seen_chapter_id", sa.Integer(), sa.ForeignKey("chapter.id")), sa.Column("first_seen_chunk_id", sa.Integer(), sa.ForeignKey("translation_chunk.id")), sa.Column("created_by_model", sa.String(255)), sa.Column("prompt_version", sa.String(128)), *_timestamps(), sa.UniqueConstraint("novel_id", "source_term"))
    op.create_index("ix_term_match", "terminology", ["novel_id", "status", "source_term"])
    op.create_table("relationship", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novel.id"), nullable=False), sa.Column("subject_entity_id", sa.Integer(), sa.ForeignKey("entity.id"), nullable=False), sa.Column("predicate", sa.String(128), nullable=False), sa.Column("object_entity_id", sa.Integer(), sa.ForeignKey("entity.id"), nullable=False), sa.Column("description", sa.Text()), sa.Column("status", sa.String(32), nullable=False), sa.Column("first_seen_chapter_id", sa.Integer(), sa.ForeignKey("chapter.id")), sa.Column("first_seen_chunk_id", sa.Integer(), sa.ForeignKey("translation_chunk.id")), sa.Column("confidence", sa.Float(), nullable=False), *_timestamps(), sa.UniqueConstraint("novel_id", "subject_entity_id", "predicate", "object_entity_id"))
    op.create_table("addressing_rule", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novel.id"), nullable=False), sa.Column("speaker_entity_id", sa.Integer(), sa.ForeignKey("entity.id")), sa.Column("listener_entity_id", sa.Integer(), sa.ForeignKey("entity.id")), sa.Column("speaker_pronoun", sa.String(128)), sa.Column("listener_pronoun", sa.String(128)), sa.Column("source_title", sa.String(512)), sa.Column("translated_title", sa.String(512)), sa.Column("description", sa.Text()), sa.Column("status", sa.String(32), nullable=False), sa.Column("first_seen_chapter_id", sa.Integer(), sa.ForeignKey("chapter.id")), sa.Column("first_seen_chunk_id", sa.Integer(), sa.ForeignKey("translation_chunk.id")), *_timestamps())
    op.create_table("context_fact", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novel.id"), nullable=False), sa.Column("subject", sa.String(512), nullable=False), sa.Column("fact_key", sa.String(512), nullable=False), sa.Column("fact_value", sa.Text(), nullable=False), sa.Column("description", sa.Text()), sa.Column("status", sa.String(32), nullable=False), sa.Column("first_seen_chapter_id", sa.Integer(), sa.ForeignKey("chapter.id")), sa.Column("first_seen_chunk_id", sa.Integer(), sa.ForeignKey("translation_chunk.id")), sa.Column("confidence", sa.Float(), nullable=False), *_timestamps(), sa.UniqueConstraint("novel_id", "subject", "fact_key"))
    op.create_table("context_conflict", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("novel_id", sa.Integer(), sa.ForeignKey("novel.id"), nullable=False), sa.Column("context_type", sa.String(32), nullable=False), sa.Column("source_key", sa.String(512), nullable=False), sa.Column("existing_value", sa.Text()), sa.Column("candidate_value", sa.Text()), sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapter.id")), sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("translation_chunk.id")), sa.Column("status", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("resolved_at", sa.DateTime()))


def downgrade() -> None:
    for table in ("context_conflict", "context_fact", "addressing_rule", "relationship", "terminology", "entity_alias", "entity", "translation_chunk", "translation_job", "chapter", "novel"):
        op.drop_table(table)
