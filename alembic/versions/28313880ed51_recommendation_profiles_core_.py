"""recommendation_profiles core_personality_id nullable

Revision ID: 28313880ed51
Revises: e0d8e3049903
Create Date: 2026-09-23 12:26:34.340111

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28313880ed51'
down_revision: Union[str, Sequence[str], None] = 'e0d8e3049903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "recommendation_profiles", "core_personality_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "recommendation_profiles", "core_personality_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )
