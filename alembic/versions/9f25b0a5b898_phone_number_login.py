"""phone_number_login

Revision ID: 9f25b0a5b898
Revises: 15b79f06a12e
Create Date: 2026-10-02 00:00:00.000000

Switches the login identity from email to phone_number (see
app/models/user.py). email becomes optional — kept only for Xendit
checkout/invoicing, which now fall back to phone_number when it's null.

Existing rows have no real phone number to backfill from, so they get a
unique numeric placeholder (row order, zero-padded) purely so the new
NOT NULL + UNIQUE constraint can apply; a real user would set their actual
phone_number by registering against the new flow, not by having one of
these placeholders.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f25b0a5b898'
down_revision: Union[str, Sequence[str], None] = '15b79f06a12e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('phone_number', sa.String(), nullable=True))

    op.execute("""
        UPDATE users SET phone_number = sub.placeholder
        FROM (
            SELECT id, lpad(row_number() OVER (ORDER BY created_at)::text, 11, '0') AS placeholder
            FROM users
        ) sub
        WHERE users.id = sub.id
    """)

    op.alter_column('users', 'phone_number', nullable=False)
    op.create_unique_constraint('uq_users_phone_number', 'users', ['phone_number'])
    op.create_index('ix_users_phone_number', 'users', ['phone_number'])

    op.alter_column('users', 'email', nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('users', 'email', nullable=False)
    op.drop_index('ix_users_phone_number', table_name='users')
    op.drop_constraint('uq_users_phone_number', 'users', type_='unique')
    op.drop_column('users', 'phone_number')
