"""Phase 2 Milestone 2: regression policies + regression result fields.

Revision ID: 0005_regression
Revises: 0004_experiments
Create Date: 2026-09-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_regression"
down_revision: Union[str, None] = "0004_experiments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "regression_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_name", sa.String(length=128), nullable=False),
        sa.Column("max_allowed_drop", sa.Float(), nullable=False),
        sa.Column("min_aggregate_score", sa.Float(), nullable=True),
        sa.Column("max_regressed_cases", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id", "metric_name", name="uq_experiment_metric_policy"),
    )
    op.create_index("ix_regression_policies_experiment_id", "regression_policies", ["experiment_id"])

    op.add_column(
        "evaluation_runs",
        sa.Column(
            "regression_status",
            sa.String(length=32),
            nullable=False,
            server_default="NOT_EVALUATED",
        ),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("regression_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.add_column(
        "case_results",
        sa.Column("is_regression", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("case_results", "is_regression")
    op.drop_column("evaluation_runs", "regression_summary")
    op.drop_column("evaluation_runs", "regression_status")
    op.drop_index("ix_regression_policies_experiment_id", table_name="regression_policies")
    op.drop_table("regression_policies")
