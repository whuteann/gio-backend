"""merge lumenart and account-link heads

Revision ID: 21083d34138d
Revises: 5b95d6775327, a1b2c3d4e5f6
Create Date: 2026-10-06 14:40:50.623855

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21083d34138d'
down_revision: Union[str, Sequence[str], None] = ('5b95d6775327', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
