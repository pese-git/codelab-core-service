"""add unique constraint on (user_id, name) for user_projects

Revision ID: 003
Revises: 002
Create Date: 2026-02-18 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraint on (user_id, name) to ensure only one project per name per user."""
    op.create_unique_constraint(
        'uq_user_projects_user_id_name',
        'user_projects',
        ['user_id', 'name']
    )


def downgrade() -> None:
    """Remove unique constraint."""
    op.drop_constraint('uq_user_projects_user_id_name', 'user_projects', type_='unique')
