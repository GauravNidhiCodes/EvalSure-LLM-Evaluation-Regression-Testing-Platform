"""Hardening: indexes and experiment name uniqueness.

Revision ID: 0007_hardening
Revises: 0006_traces
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0007_hardening"
down_revision: Union[str, None] = "0006_traces"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: local DBs may already have this index from earlier apply attempts.
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_evaluation_runs_status "
            "ON evaluation_runs (status)"
        )
    )
    op.execute(
        text(
            "DO $$ BEGIN "
            "ALTER TABLE experiments "
            "ADD CONSTRAINT uq_experiment_project_name UNIQUE (project_id, name); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "END $$"
        )
    )


def downgrade() -> None:
    op.execute(
        text(
            "ALTER TABLE experiments DROP CONSTRAINT IF EXISTS uq_experiment_project_name"
        )
    )
    op.execute(text("DROP INDEX IF EXISTS ix_evaluation_runs_status"))
