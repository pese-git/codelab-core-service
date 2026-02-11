"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-02-11 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables for the initial schema."""
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_users_email', 'users', ['email'])
    
    # Create user_orchestrators table
    op.create_table(
        'user_orchestrators',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_user_orchestrators_id', 'user_orchestrators', ['id'])
    op.create_index('ix_user_orchestrators_user_id', 'user_orchestrators', ['user_id'])
    
    # Create user_agents table
    op.create_table(
        'user_agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_agents_id', 'user_agents', ['id'])
    op.create_index('ix_user_agents_user_id', 'user_agents', ['user_id'])
    op.create_index('ix_user_agents_status', 'user_agents', ['status'])
    op.create_index('ix_user_agents_user_id_name', 'user_agents', ['user_id', 'name'])
    op.create_index('ix_user_agents_user_id_status', 'user_agents', ['user_id', 'status'])
    
    # Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_sessions_id', 'chat_sessions', ['id'])
    op.create_index('ix_chat_sessions_user_id', 'chat_sessions', ['user_id'])
    op.create_index('ix_chat_sessions_user_id_created_at', 'chat_sessions', ['user_id', 'created_at'])
    
    # Create approval_requests table
    op.create_table(
        'approval_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('payload', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_approval_requests_id', 'approval_requests', ['id'])
    op.create_index('ix_approval_requests_user_id', 'approval_requests', ['user_id'])
    op.create_index('ix_approval_requests_status', 'approval_requests', ['status'])
    op.create_index('ix_approval_requests_user_id_status', 'approval_requests', ['user_id', 'status'])
    op.create_index('ix_approval_requests_status_created_at', 'approval_requests', ['status', 'created_at'])
    
    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['user_agents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_messages_id', 'messages', ['id'])
    op.create_index('ix_messages_session_id', 'messages', ['session_id'])
    op.create_index('ix_messages_agent_id', 'messages', ['agent_id'])
    op.create_index('ix_messages_session_id_created_at', 'messages', ['session_id', 'created_at'])
    op.create_index('ix_messages_agent_id_created_at', 'messages', ['agent_id', 'created_at'])
    
    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('result', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['user_agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tasks_id', 'tasks', ['id'])
    op.create_index('ix_tasks_session_id', 'tasks', ['session_id'])
    op.create_index('ix_tasks_agent_id', 'tasks', ['agent_id'])
    op.create_index('ix_tasks_status', 'tasks', ['status'])
    op.create_index('ix_tasks_session_id_status', 'tasks', ['session_id', 'status'])
    op.create_index('ix_tasks_agent_id_status', 'tasks', ['agent_id', 'status'])
    op.create_index('ix_tasks_status_created_at', 'tasks', ['status', 'created_at'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('tasks')
    op.drop_table('messages')
    op.drop_table('approval_requests')
    op.drop_table('chat_sessions')
    op.drop_table('user_agents')
    op.drop_table('user_orchestrators')
    op.drop_table('users')
