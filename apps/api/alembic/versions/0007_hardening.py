"""Hardening: indexes and experiment name uniqueness.

Revision ID: 0007_hardening
Revises: 0006_traces
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_hardening"
down_revision: Union[str, None] = "0006_traces"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"], unique=False)
    op.create_unique_constraint(
        "uq_experiment_project_name",
        "experiments",
        ["project_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_experiment_project_name", "experiments", type_="unique")
    op.drop_index("ix_evaluation_runs_status", table_name="evaluation_runs")
