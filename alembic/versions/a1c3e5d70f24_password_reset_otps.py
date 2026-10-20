"""password reset otps

Revision ID: a1c3e5d70f24
Revises: 40486e5c4908
Create Date: 2026-10-20 04:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1c3e5d70f24'
down_revision: Union[str, Sequence[str], None] = '40486e5c4908'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "password_reset_otps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False, server_default="password_reset"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_password_reset_otps_user_id", "password_reset_otps", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_password_reset_otps_user_id", table_name="password_reset_otps")
    op.drop_table("password_reset_otps")
