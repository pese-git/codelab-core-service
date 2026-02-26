"""add_event_outbox_table

Revision ID: 006_event_outbox
Revises: f9db44130792
Create Date: 2026-02-26 23:45:38.000000+03:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '006_event_outbox'
down_revision: str | None = 'f9db44130792'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create event_outbox table for transactional event publishing."""
    op.create_table(
        'event_outbox',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('aggregate_type', sa.String(length=50), nullable=False),
        sa.Column('aggregate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('next_retry_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('published_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create indexes
    op.create_index('ix_event_outbox_id', 'event_outbox', ['id'], unique=False)
    op.create_index('ix_event_outbox_aggregate_type', 'event_outbox', ['aggregate_type'], unique=False)
    op.create_index('ix_event_outbox_aggregate_id', 'event_outbox', ['aggregate_id'], unique=False)
    op.create_index('ix_event_outbox_user_id', 'event_outbox', ['user_id'], unique=False)
    op.create_index('ix_event_outbox_project_id', 'event_outbox', ['project_id'], unique=False)
    op.create_index('ix_event_outbox_status', 'event_outbox', ['status'], unique=False)
    op.create_index('ix_event_outbox_next_retry_at', 'event_outbox', ['next_retry_at'], unique=False)
    op.create_index('ix_event_outbox_created_at', 'event_outbox', ['created_at'], unique=False)
    
    # Composite indexes for efficient querying
    op.create_index(
        'ix_event_outbox_status_next_retry_created',
        'event_outbox',
        ['status', 'next_retry_at', 'created_at'],
        unique=False
    )
    op.create_index(
        'ix_event_outbox_aggregate_id_created',
        'event_outbox',
        ['aggregate_id', 'created_at'],
        unique=False
    )
    op.create_index(
        'ix_event_outbox_project_id_created',
        'event_outbox',
        ['project_id', 'created_at'],
        unique=False
    )
    op.create_index(
        'ix_event_outbox_user_id_created',
        'event_outbox',
        ['user_id', 'created_at'],
        unique=False
    )


def downgrade() -> None:
    """Drop event_outbox table and indexes."""
    op.drop_index('ix_event_outbox_user_id_created', table_name='event_outbox')
    op.drop_index('ix_event_outbox_project_id_created', table_name='event_outbox')
    op.drop_index('ix_event_outbox_aggregate_id_created', table_name='event_outbox')
    op.drop_index('ix_event_outbox_status_next_retry_created', table_name='event_outbox')
    op.drop_index('ix_event_outbox_created_at', table_name='event_outbox')
    op.drop_index('ix_event_outbox_next_retry_at', table_name='event_outbox')
    op.drop_index('ix_event_outbox_status', table_name='event_outbox')
    op.drop_index('ix_event_outbox_project_id', table_name='event_outbox')
    op.drop_index('ix_event_outbox_user_id', table_name='event_outbox')
    op.drop_index('ix_event_outbox_aggregate_id', table_name='event_outbox')
    op.drop_index('ix_event_outbox_aggregate_type', table_name='event_outbox')
    op.drop_index('ix_event_outbox_id', table_name='event_outbox')
    op.drop_table('event_outbox')
