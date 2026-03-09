"""add_llm_providers_tables

Revision ID: 008_llm_providers
Revises: 007_tool_executions
Create Date: 2026-03-09 06:48:00.000000+03:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "008_llm_providers"
down_revision: str | None = "007_tool_executions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create user_llm_providers and llm_provider_audit_log tables."""
    
    # Create user_llm_providers table
    op.create_table(
        "user_llm_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("litellm_model_name", sa.String(length=255), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    
    op.create_index("ix_user_llm_providers_id", "user_llm_providers", ["id"], unique=False)
    op.create_index("ix_user_llm_providers_user_id", "user_llm_providers", ["user_id"], unique=False)
    op.create_index("ix_user_llm_providers_provider_type", "user_llm_providers", ["provider_type"], unique=False)
    op.create_index(
        "ix_user_llm_providers_user_created",
        "user_llm_providers",
        ["user_id", "created_at"],
        unique=False,
    )
    
    # Create llm_provider_audit_log table
    op.create_table(
        "llm_provider_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("old_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["user_llm_providers.id"], ondelete="SET NULL"),
    )
    
    op.create_index("ix_llm_provider_audit_log_id", "llm_provider_audit_log", ["id"], unique=False)
    op.create_index("ix_llm_provider_audit_log_user_id", "llm_provider_audit_log", ["user_id"], unique=False)
    op.create_index("ix_llm_provider_audit_log_provider_id", "llm_provider_audit_log", ["provider_id"], unique=False)
    op.create_index("ix_llm_provider_audit_log_action", "llm_provider_audit_log", ["action"], unique=False)
    op.create_index(
        "ix_llm_provider_audit_log_user_created",
        "llm_provider_audit_log",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_llm_provider_audit_log_action_created",
        "llm_provider_audit_log",
        ["action", "created_at"],
        unique=False,
    )
    
    # Add llm_provider_id column to user_agents table
    op.add_column(
        "user_agents",
        sa.Column("llm_provider_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_user_agents_llm_provider_id",
        "user_agents",
        "user_llm_providers",
        ["llm_provider_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_user_agents_llm_provider_id", "user_agents", ["llm_provider_id"], unique=False)


def downgrade() -> None:
    """Drop llm_providers tables and revert agent changes."""
    
    # Remove llm_provider_id from user_agents
    op.drop_index("ix_user_agents_llm_provider_id", table_name="user_agents")
    op.drop_constraint("fk_user_agents_llm_provider_id", "user_agents", type_="foreignkey")
    op.drop_column("user_agents", "llm_provider_id")
    
    # Drop llm_provider_audit_log
    op.drop_index("ix_llm_provider_audit_log_action_created", table_name="llm_provider_audit_log")
    op.drop_index("ix_llm_provider_audit_log_user_created", table_name="llm_provider_audit_log")
    op.drop_index("ix_llm_provider_audit_log_action", table_name="llm_provider_audit_log")
    op.drop_index("ix_llm_provider_audit_log_provider_id", table_name="llm_provider_audit_log")
    op.drop_index("ix_llm_provider_audit_log_user_id", table_name="llm_provider_audit_log")
    op.drop_index("ix_llm_provider_audit_log_id", table_name="llm_provider_audit_log")
    op.drop_table("llm_provider_audit_log")
    
    # Drop user_llm_providers
    op.drop_index("ix_user_llm_providers_user_created", table_name="user_llm_providers")
    op.drop_index("ix_user_llm_providers_provider_type", table_name="user_llm_providers")
    op.drop_index("ix_user_llm_providers_user_id", table_name="user_llm_providers")
    op.drop_index("ix_user_llm_providers_id", table_name="user_llm_providers")
    op.drop_table("user_llm_providers")
