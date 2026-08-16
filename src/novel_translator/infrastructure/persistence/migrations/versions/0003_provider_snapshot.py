"""Store global provider identity on translation jobs."""

import sqlalchemy as sa
from alembic import op

revision = "0003_provider_snapshot"
down_revision = "0002_model_call"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("translation_job", sa.Column("profile_id", sa.String(128), nullable=True))
    op.add_column("translation_job", sa.Column("config_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("translation_job", "config_hash")
    op.drop_column("translation_job", "profile_id")
