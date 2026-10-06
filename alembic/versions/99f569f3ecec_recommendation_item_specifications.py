"""recommendation_item_specifications

Revision ID: 99f569f3ecec
Revises: c3602460f2af
Create Date: 2026-10-05 00:00:00.000000

Adds RecommendationItem.specifications — the vendor product's own
specifications (Materials/Certification/Inner Diameter etc.), cleaned and
already zh/en split by app/services/product_api.py::parse_specifications().
Purely additive, nullable, no data migration needed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '99f569f3ecec'
down_revision: Union[str, Sequence[str], None] = 'c3602460f2af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('recommendation_items', sa.Column('specifications', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('recommendation_items', 'specifications')
