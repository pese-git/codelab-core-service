"""Add task_plans and task_plan_tasks tables for orchestrator

Revision ID: 004
Revises: 003
Create Date: 2026-02-20 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create task_plans and task_plan_tasks tables."""
    # Create task_plans table
    op.create_table(
        'task_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_request', sa.String(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='created'),
        sa.Column('total_estimated_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_estimated_duration', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('approval_reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['user_projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create indexes for task_plans
    op.create_index('ix_task_plans_id', 'task_plans', ['id'], unique=False)
    op.create_index('ix_task_plans_user_id_project_id', 'task_plans', ['user_id', 'project_id'], unique=False)
    op.create_index('ix_task_plans_session_id', 'task_plans', ['session_id'], unique=False)
    op.create_index('ix_task_plans_status', 'task_plans', ['status'], unique=False)
    op.create_index('ix_task_plans_status_created_at', 'task_plans', ['status', 'created_at'], unique=False)

    # Create task_plan_tasks table
    op.create_table(
        'task_plan_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', sa.String(50), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('dependencies', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('estimated_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('estimated_duration', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('risk_level', sa.String(10), nullable=False, server_default='LOW'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('result', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['task_plans.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['user_agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create indexes for task_plan_tasks
    op.create_index('ix_task_plan_tasks_id', 'task_plan_tasks', ['id'], unique=False)
    op.create_index('ix_task_plan_tasks_plan_id', 'task_plan_tasks', ['plan_id'], unique=False)
    op.create_index('ix_task_plan_tasks_agent_id', 'task_plan_tasks', ['agent_id'], unique=False)
    op.create_index('ix_task_plan_tasks_status', 'task_plan_tasks', ['status'], unique=False)


def downgrade() -> None:
    """Drop task_plans and task_plan_tasks tables."""
    # Drop indexes for task_plan_tasks
    op.drop_index('ix_task_plan_tasks_status', table_name='task_plan_tasks')
    op.drop_index('ix_task_plan_tasks_agent_id', table_name='task_plan_tasks')
    op.drop_index('ix_task_plan_tasks_plan_id', table_name='task_plan_tasks')
    op.drop_index('ix_task_plan_tasks_id', table_name='task_plan_tasks')

    # Drop task_plan_tasks table
    op.drop_table('task_plan_tasks')

    # Drop indexes for task_plans
    op.drop_index('ix_task_plans_status_created_at', table_name='task_plans')
    op.drop_index('ix_task_plans_status', table_name='task_plans')
    op.drop_index('ix_task_plans_session_id', table_name='task_plans')
    op.drop_index('ix_task_plans_user_id_project_id', table_name='task_plans')
    op.drop_index('ix_task_plans_id', table_name='task_plans')

    # Drop task_plans table
    op.drop_table('task_plans')
