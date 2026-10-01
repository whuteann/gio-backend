"""core_personality_number_points

Revision ID: 13ea5cd95299
Revises: 8a82d868a7c5
Create Date: 2026-10-01 00:00:00.000000

Replaces CorePersonality's paragraph-style *_number_content_{en,zh} String
columns with *_number_points_{en,zh} JSONB columns (arrays of
{"emoji", "text"} objects) — see app/services/ai_personality.py's prompt
redesign. No data migration: existing rows' old paragraph content isn't in
the new point-form shape, so this is forward-only — existing users keep
whatever generation_status/other fields they have, just with empty number
points until/unless Core Personality is regenerated for them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '13ea5cd95299'
down_revision: Union[str, Sequence[str], None] = '8a82d868a7c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('core_personalities', 'birthday_number_content_en')
    op.drop_column('core_personalities', 'birthday_number_content_zh')
    op.drop_column('core_personalities', 'life_path_number_content_en')
    op.drop_column('core_personalities', 'life_path_number_content_zh')
    op.drop_column('core_personalities', 'talent_number_content_en')
    op.drop_column('core_personalities', 'talent_number_content_zh')

    op.add_column('core_personalities', sa.Column('birthday_number_points_en', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('core_personalities', sa.Column('birthday_number_points_zh', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('core_personalities', sa.Column('life_path_number_points_en', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('core_personalities', sa.Column('life_path_number_points_zh', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('core_personalities', sa.Column('talent_number_points_en', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('core_personalities', sa.Column('talent_number_points_zh', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('core_personalities', 'talent_number_points_zh')
    op.drop_column('core_personalities', 'talent_number_points_en')
    op.drop_column('core_personalities', 'life_path_number_points_zh')
    op.drop_column('core_personalities', 'life_path_number_points_en')
    op.drop_column('core_personalities', 'birthday_number_points_zh')
    op.drop_column('core_personalities', 'birthday_number_points_en')

    op.add_column('core_personalities', sa.Column('talent_number_content_zh', sa.String(), nullable=True))
    op.add_column('core_personalities', sa.Column('talent_number_content_en', sa.String(), nullable=True))
    op.add_column('core_personalities', sa.Column('life_path_number_content_zh', sa.String(), nullable=True))
    op.add_column('core_personalities', sa.Column('life_path_number_content_en', sa.String(), nullable=True))
    op.add_column('core_personalities', sa.Column('birthday_number_content_zh', sa.String(), nullable=True))
    op.add_column('core_personalities', sa.Column('birthday_number_content_en', sa.String(), nullable=True))
