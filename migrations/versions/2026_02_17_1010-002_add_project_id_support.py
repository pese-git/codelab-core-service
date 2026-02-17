"""add project_id support for per-project architecture

Revision ID: 002
Revises: 001
Create Date: 2026-02-17 10:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add project_id support for per-project architecture."""
    
    # 1. Create user_projects table
    op.create_table(
        'user_projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('workspace_path', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_projects_id', 'user_projects', ['id'])
    op.create_index('ix_user_projects_user_id', 'user_projects', ['user_id'])
    op.create_index('ix_user_projects_user_id_name', 'user_projects', ['user_id', 'name'])
    op.create_index('ix_user_projects_user_id_created_at', 'user_projects', ['user_id', 'created_at'])

    # 2. Add project_id to user_agents
    # First add as nullable
    op.add_column('user_agents',
                  sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Create default project for each user with raw connection
    # We need to execute raw SQL to avoid asyncpg query preparation issues
    conn = op.get_bind()
    
    # Create a project for each user in the database
    project_sql = """
        INSERT INTO user_projects (id, user_id, name, created_at, updated_at)
        SELECT gen_random_uuid(), u.id, 'Default Project', NOW(), NOW()
        FROM users u
    """
    
    # Use raw SQL without parameters to avoid asyncpg prepare issues
    conn.exec_driver_sql(project_sql)
    
    # Assign agents to default projects
    update_agents_sql = """
        UPDATE user_agents ua
        SET project_id = up.id
        FROM user_projects up
        WHERE ua.user_id = up.user_id AND up.name = 'Default Project'
    """
    conn.exec_driver_sql(update_agents_sql)

    # Now make project_id NOT NULL and add FK
    op.alter_column('user_agents', 'project_id', nullable=False)
    op.create_foreign_key('fk_user_agents_project_id', 'user_agents', 'user_projects',
                          ['project_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_user_agents_project_id', 'user_agents', ['project_id'])
    
    # Update composite index
    op.drop_index('ix_user_agents_user_id_name', table_name='user_agents')
    op.create_index('ix_user_agents_user_id_project_id_name', 'user_agents',
                    ['user_id', 'project_id', 'name'])
    op.create_index('ix_user_agents_project_id_status', 'user_agents',
                    ['project_id', 'status'])

    # 3. Add project_id to chat_sessions
    # First add as nullable
    op.add_column('chat_sessions',
                  sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Assign sessions to same project as their user's default project
    update_sessions_sql = """
        UPDATE chat_sessions cs
        SET project_id = up.id
        FROM user_projects up
        WHERE cs.user_id = up.user_id AND up.name = 'Default Project'
    """
    conn.exec_driver_sql(update_sessions_sql)

    # Make project_id NOT NULL and add FK
    op.alter_column('chat_sessions', 'project_id', nullable=False)
    op.create_foreign_key('fk_chat_sessions_project_id', 'chat_sessions', 'user_projects',
                          ['project_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_chat_sessions_project_id', 'chat_sessions', ['project_id'])
    
    # Update composite indexes
    op.drop_index('ix_chat_sessions_user_id_created_at', table_name='chat_sessions')
    op.create_index('ix_chat_sessions_user_id_project_id_created_at', 'chat_sessions',
                    ['user_id', 'project_id', 'created_at'])
    op.create_index('ix_chat_sessions_project_id_created_at', 'chat_sessions',
                    ['project_id', 'created_at'])

    # 4. Add project_id to user_orchestrators
    # First add as nullable
    op.add_column('user_orchestrators',
                  sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Assign orchestrators to same project as their user's default project
    update_orch_sql = """
        UPDATE user_orchestrators uo
        SET project_id = up.id
        FROM user_projects up
        WHERE uo.user_id = up.user_id AND up.name = 'Default Project'
    """
    conn.exec_driver_sql(update_orch_sql)

    # Make project_id NOT NULL and add FK
    op.alter_column('user_orchestrators', 'project_id', nullable=False)
    op.create_foreign_key('fk_user_orchestrators_project_id', 'user_orchestrators', 'user_projects',
                          ['project_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_user_orchestrators_project_id', 'user_orchestrators', ['project_id'])
    
    # Update composite index - remove unique constraint on user_id since now it's per-project
    op.drop_constraint('user_orchestrators_user_id_key', 'user_orchestrators', type_='unique')
    
    # Add new composite index
    op.drop_index('ix_user_orchestrators_user_id', table_name='user_orchestrators')
    op.create_index('ix_user_orchestrators_user_id_project_id', 'user_orchestrators',
                    ['user_id', 'project_id'])


def downgrade() -> None:
    """Downgrade: remove project_id support."""
    
    # Drop indexes in reverse order
    op.drop_index('ix_user_orchestrators_user_id_project_id', table_name='user_orchestrators')
    op.drop_index('ix_user_orchestrators_project_id', table_name='user_orchestrators')
    
    # Re-add unique constraint on user_id
    op.create_unique_constraint('user_orchestrators_user_id_key', 'user_orchestrators', ['user_id'])
    op.create_index('ix_user_orchestrators_user_id', 'user_orchestrators', ['user_id'])
    
    # Drop FK and column from user_orchestrators
    op.drop_constraint('fk_user_orchestrators_project_id', 'user_orchestrators', type_='foreignkey')
    op.drop_column('user_orchestrators', 'project_id')

    # Drop indexes from chat_sessions
    op.drop_index('ix_chat_sessions_project_id_created_at', table_name='chat_sessions')
    op.drop_index('ix_chat_sessions_user_id_project_id_created_at', table_name='chat_sessions')
    op.drop_index('ix_chat_sessions_project_id', table_name='chat_sessions')
    
    # Drop FK and column from chat_sessions
    op.drop_constraint('fk_chat_sessions_project_id', 'chat_sessions', type_='foreignkey')
    op.drop_column('chat_sessions', 'project_id')
    
    # Re-add original index
    op.create_index('ix_chat_sessions_user_id_created_at', 'chat_sessions', ['user_id', 'created_at'])

    # Drop indexes from user_agents
    op.drop_index('ix_user_agents_project_id_status', table_name='user_agents')
    op.drop_index('ix_user_agents_user_id_project_id_name', table_name='user_agents')
    op.drop_index('ix_user_agents_project_id', table_name='user_agents')
    
    # Drop FK and column from user_agents
    op.drop_constraint('fk_user_agents_project_id', 'user_agents', type_='foreignkey')
    op.drop_column('user_agents', 'project_id')
    
    # Re-add original index
    op.create_index('ix_user_agents_user_id_name', 'user_agents', ['user_id', 'name'])

    # Drop user_projects table and its indexes
    op.drop_index('ix_user_projects_user_id_created_at', table_name='user_projects')
    op.drop_index('ix_user_projects_user_id_name', table_name='user_projects')
    op.drop_index('ix_user_projects_user_id', table_name='user_projects')
    op.drop_index('ix_user_projects_id', table_name='user_projects')
    op.drop_table('user_projects')
