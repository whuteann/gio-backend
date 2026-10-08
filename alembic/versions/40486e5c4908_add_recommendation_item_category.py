"""add recommendation item category

Revision ID: 40486e5c4908
Revises: 21083d34138d
Create Date: 2026-10-08 09:41:10.164934

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '40486e5c4908'
down_revision: Union[str, Sequence[str], None] = '21083d34138d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("recommendation_items", sa.Column("category", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("recommendation_items", "category")
