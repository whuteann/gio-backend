"""user email verification flag

Revision ID: e4a71c9b2d05
Revises: c7f2b9a04d31
Create Date: 2026-10-21 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e4a71c9b2d05'
down_revision: Union[str, Sequence[str], None] = 'c7f2b9a04d31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    # Every account that already exists is treated as verified. Leaving them
    # null would bounce the entire existing user base into an OTP flow for an
    # address most of them never supplied — email only became a required
    # signup field recently. Only signups after this migration start
    # unverified. created_at is used as the timestamp because it is the only
    # honest one available: we do not know when, only that it predates this.
    op.execute("UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "email_verified_at")
