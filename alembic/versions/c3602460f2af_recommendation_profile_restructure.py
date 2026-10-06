"""recommendation_profile_restructure

Revision ID: c3602460f2af
Revises: 9f25b0a5b898
Create Date: 2026-10-05 00:00:00.000000

Adds RecommendationProfile.material_affinity (the deterministic stone-type
pick — Crystal/Nephrite/Jade) and .letter_en/.letter_zh (the AI half's one
unifying letter) — see docs/recommendation_engine.md and
app/services/ai_recommendation.py. Purely additive, all nullable, no data
migration needed; RecommendationItem.type already a free string column so
the new "PHONE_CASE" value needs no schema change at all.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3602460f2af'
down_revision: Union[str, Sequence[str], None] = '9f25b0a5b898'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('recommendation_profiles', sa.Column('material_affinity', sa.String(), nullable=True))
    op.add_column('recommendation_profiles', sa.Column('letter_en', sa.String(), nullable=True))
    op.add_column('recommendation_profiles', sa.Column('letter_zh', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('recommendation_profiles', 'letter_zh')
    op.drop_column('recommendation_profiles', 'letter_en')
    op.drop_column('recommendation_profiles', 'material_affinity')
