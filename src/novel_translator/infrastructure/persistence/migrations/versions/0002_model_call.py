"""Add model-call audit records for the desktop inspector.

Revision ID: 0002_model_call
Revises: 0001_initial
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_model_call"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_call",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("translation_job_id", sa.Integer(), sa.ForeignKey("translation_job.id"), nullable=False),
        sa.Column("translation_chunk_id", sa.Integer(), sa.ForeignKey("translation_chunk.id"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("prompt_version", sa.String(128), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("context_snapshot_json", sa.JSON()),
        sa.Column("previous_translation_tail", sa.Text(), nullable=False, server_default=""),
        sa.Column("response_json", sa.JSON()),
        sa.Column("translated_text", sa.Text()),
        sa.Column("diagnostic_json", sa.JSON()),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_model_call_job", "model_call", ["translation_job_id"])
    op.create_index("ix_model_call_chunk", "model_call", ["translation_chunk_id", "attempt_number"])
    op.create_index("ix_model_call_status", "model_call", ["status"])


def downgrade() -> None:
    op.drop_index("ix_model_call_status", table_name="model_call")
    op.drop_index("ix_model_call_chunk", table_name="model_call")
    op.drop_index("ix_model_call_job", table_name="model_call")
    op.drop_table("model_call")
