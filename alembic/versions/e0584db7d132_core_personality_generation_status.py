"""core personality generation status columns

Revision ID: e0584db7d132
Revises: 01aec548f3cc
Create Date: 2026-09-23 02:00:00.000000

Adds primary_language and generation_status to core_personalities, needed
for the sequential dual-language generation flow (see
docs/behaviour_log_0004.md) — additive only, no drop/recreate needed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e0584db7d132'
down_revision: Union[str, Sequence[str], None] = '01aec548f3cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('core_personalities', sa.Column('primary_language', sa.String(), nullable=True))
    op.add_column('core_personalities', sa.Column('generation_status', sa.String(), nullable=False, server_default='PARTIAL'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('core_personalities', 'generation_status')
    op.drop_column('core_personalities', 'primary_language')
