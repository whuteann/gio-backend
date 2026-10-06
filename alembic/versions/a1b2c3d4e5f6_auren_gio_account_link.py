"""link gio-backend users to a bracelet (Gio) account

Revision ID: a1b2c3d4e5f6
Revises: 99f569f3ecec
Create Date: 2026-10-05 00:00:00.000000

See AUREN_GIO_ACCOUNT_LINKING_PLAN.md at the repo root — this is the
Auren-side mirror of braceletBackend's auren_account_links table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '99f569f3ecec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('linked_bracelet_user_id', sa.UUID(), nullable=True))
    op.add_column('users', sa.Column('linked_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(
        'uq_users_linked_bracelet_user_id', 'users', ['linked_bracelet_user_id']
    )


def downgrade() -> None:
    op.drop_constraint('uq_users_linked_bracelet_user_id', 'users', type_='unique')
    op.drop_column('users', 'linked_at')
    op.drop_column('users', 'linked_bracelet_user_id')
