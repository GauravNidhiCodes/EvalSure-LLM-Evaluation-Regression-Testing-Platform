"""Phase 2 Milestone 1: experiments + baseline_run_id on experiments.

Revision ID: 0004_experiments
Revises: 0003_evaluation_runs
Create Date: 2026-09-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_experiments"
down_revision: Union[str, None] = "0003_evaluation_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_experiments_project_id", "experiments", ["project_id"], unique=False)

    op.add_column(
        "evaluation_runs",
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_evaluation_runs_experiment_id", "evaluation_runs", ["experiment_id"], unique=False)
    op.create_foreign_key(
        "fk_evaluation_runs_experiment_id",
        "evaluation_runs",
        "experiments",
        ["experiment_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "experiments",
        sa.Column("baseline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_experiments_baseline_run_id", "experiments", ["baseline_run_id"], unique=False)
    op.create_foreign_key(
        "fk_experiments_baseline_run_id",
        "experiments",
        "evaluation_runs",
        ["baseline_run_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_experiments_baseline_run_id", "experiments", type_="foreignkey")
    op.drop_index("ix_experiments_baseline_run_id", table_name="experiments")
    op.drop_column("experiments", "baseline_run_id")

    op.drop_constraint("fk_evaluation_runs_experiment_id", "evaluation_runs", type_="foreignkey")
    op.drop_index("ix_evaluation_runs_experiment_id", table_name="evaluation_runs")
    op.drop_column("evaluation_runs", "experiment_id")

    op.drop_index("ix_experiments_project_id", table_name="experiments")
    op.drop_table("experiments")
