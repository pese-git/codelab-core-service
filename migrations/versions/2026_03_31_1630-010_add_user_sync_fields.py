"""Add user sync fields for event-driven synchronization

Revision ID: 010_user_sync_fields
Revises: 2026_03_09_1924-009_add_unique_constraint_user_projects_name_workspace_path.py
Create Date: 2026-03-31 16:30:00.000000

Adds fields to users table for tracking synchronization with auth-service:
- synced_from_auth_at: timestamp of last synchronization
- synced_version: version counter for idempotent processing
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010_user_sync_fields'
down_revision: Union[str, None] = '009_user_projects_unique'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user sync fields to users table"""
    
    # Add synced_from_auth_at column
    op.add_column('users',
        sa.Column('synced_from_auth_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Add synced_version column for idempotent processing
    op.add_column('users',
        sa.Column('synced_version', sa.Integer(), nullable=False, server_default='0')
    )
    
    # Create index for sync tracking
    op.create_index('ix_users_synced_from_auth_at', 'users', ['synced_from_auth_at'])


def downgrade() -> None:
    """Revert user sync fields from users table"""
    
    # Drop index
    op.drop_index('ix_users_synced_from_auth_at', table_name='users')
    
    # Drop columns
    op.drop_column('users', 'synced_version')
    op.drop_column('users', 'synced_from_auth_at')
