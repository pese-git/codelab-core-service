"""add_tool_executions_table

Revision ID: 007_tool_executions
Revises: 006_event_outbox
Create Date: 2026-02-28 12:00:00.000000+03:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "007_tool_executions"
down_revision: str | None = "006_event_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create tool_executions table for tool workflow tracking."""
    op.create_table(
        "tool_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("tool_params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_tool_executions_id", "tool_executions", ["id"], unique=False)
    op.create_index("ix_tool_executions_user_id", "tool_executions", ["user_id"], unique=False)
    op.create_index("ix_tool_executions_project_id", "tool_executions", ["project_id"], unique=False)
    op.create_index("ix_tool_executions_session_id", "tool_executions", ["session_id"], unique=False)
    op.create_index("ix_tool_executions_tool_name", "tool_executions", ["tool_name"], unique=False)
    op.create_index("ix_tool_executions_status", "tool_executions", ["status"], unique=False)
    op.create_index("ix_tool_executions_created_at", "tool_executions", ["created_at"], unique=False)

    op.create_index(
        "ix_tool_exec_user_project_created",
        "tool_executions",
        ["user_id", "project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_tool_exec_project_created",
        "tool_executions",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_tool_exec_session_created",
        "tool_executions",
        ["session_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_tool_exec_status_created",
        "tool_executions",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop tool_executions table and indexes."""
    op.drop_index("ix_tool_exec_status_created", table_name="tool_executions")
    op.drop_index("ix_tool_exec_session_created", table_name="tool_executions")
    op.drop_index("ix_tool_exec_project_created", table_name="tool_executions")
    op.drop_index("ix_tool_exec_user_project_created", table_name="tool_executions")

    op.drop_index("ix_tool_executions_created_at", table_name="tool_executions")
    op.drop_index("ix_tool_executions_status", table_name="tool_executions")
    op.drop_index("ix_tool_executions_tool_name", table_name="tool_executions")
    op.drop_index("ix_tool_executions_session_id", table_name="tool_executions")
    op.drop_index("ix_tool_executions_project_id", table_name="tool_executions")
    op.drop_index("ix_tool_executions_user_id", table_name="tool_executions")
    op.drop_index("ix_tool_executions_id", table_name="tool_executions")

    op.drop_table("tool_executions")
