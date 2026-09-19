"""Phase 4 Milestone 1: evaluation traces (TraceEvent).

Revision ID: 0006_traces
Revises: 0005_regression
Create Date: 2026-09-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_traces"
down_revision: Union[str, None] = "0005_regression"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trace_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_result_id"], ["case_results.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trace_events_run_id", "trace_events", ["run_id"])
    op.create_index("ix_trace_events_case_result_id", "trace_events", ["case_result_id"])
    op.create_index("ix_trace_events_event_type", "trace_events", ["event_type"])
    op.create_index("ix_trace_events_timestamp", "trace_events", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_trace_events_timestamp", table_name="trace_events")
    op.drop_index("ix_trace_events_event_type", table_name="trace_events")
    op.drop_index("ix_trace_events_case_result_id", table_name="trace_events")
    op.drop_index("ix_trace_events_run_id", table_name="trace_events")
    op.drop_table("trace_events")
