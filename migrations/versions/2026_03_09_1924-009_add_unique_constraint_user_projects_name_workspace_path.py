"""add unique constraint on (name, workspace_path) for user_projects

Revision ID: 009_user_projects_unique
Revises: 008_llm_providers
Create Date: 2026-03-09 19:24:00.000000+03:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '009_user_projects_unique'
down_revision: Union[str, None] = '008_llm_providers'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraint on (name, workspace_path) to ensure uniqueness."""
    op.create_unique_constraint(
        'uq_user_projects_name_workspace_path',
        'user_projects',
        ['name', 'workspace_path']
    )


def downgrade() -> None:
    """Remove unique constraint."""
    op.drop_constraint('uq_user_projects_name_workspace_path', 'user_projects', type_='unique')
