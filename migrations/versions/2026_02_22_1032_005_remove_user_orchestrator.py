"""Remove UserOrchestrator model and table.

This migration removes the user_orchestrators table as we're moving to
unified UserAgent approach where Orchestrator is just a UserAgent with
role='orchestrator'.

Revision ID: 005
Revises: 004
Create Date: 2026-02-22 10:32:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop the user_orchestrators table and its index."""
    # Drop the index first
    op.drop_index(
        "ix_user_orchestrators_user_id_project_id",
        table_name="user_orchestrators",
    )
    # Drop the table
    op.drop_table("user_orchestrators")


def downgrade() -> None:
    """Recreate the user_orchestrators table for rollback."""
    op.create_table(
        "user_orchestrators",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "project_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("config", postgresql.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["user_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_orchestrators_user_id_project_id",
        "user_orchestrators",
        ["user_id", "project_id"],
    )
