"""subscription trial and weekly gating

Revision ID: ee09635a3ec5
Revises: 9a3e05e4b10a
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ee09635a3ec5'
down_revision: Union[str, Sequence[str], None] = '9a3e05e4b10a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('subscriptions', sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True))
    op.drop_column('subscriptions', 'billing_cycle')
    op.drop_column('subscriptions', 'first_free_reading_consumed_at')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('subscriptions', sa.Column('first_free_reading_consumed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('billing_cycle', sa.String(), nullable=True))
    op.drop_column('subscriptions', 'trial_ends_at')
