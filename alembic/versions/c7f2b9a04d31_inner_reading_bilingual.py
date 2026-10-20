"""inner reading bilingual content

Revision ID: c7f2b9a04d31
Revises: a1c3e5d70f24
Create Date: 2026-10-20 06:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c7f2b9a04d31'
down_revision: Union[str, Sequence[str], None] = 'a1c3e5d70f24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ZH_COLUMNS = [
    ("result_summary_zh", sa.String()),
    ("narrative_zh", sa.String()),
    ("insight_zh", sa.String()),
    ("reflection_question_zh", sa.String()),
    ("title_zh", sa.String()),
    ("subtitle_zh", sa.String()),
    ("current_focus", sa.String()),
    ("current_focus_zh", sa.String()),
    ("life_area_insights_zh", postgresql.JSONB()),
]


def upgrade() -> None:
    """Upgrade schema."""
    for name, type_ in _ZH_COLUMNS:
        op.add_column("inner_readings", sa.Column(name, type_, nullable=True))
    op.add_column("inner_readings", sa.Column("primary_language", sa.String(), nullable=True))
    op.add_column(
        "inner_readings",
        sa.Column("generation_status", sa.String(), nullable=False, server_default="PARTIAL"),
    )
    # Every reading written before this migration was generated in English
    # only, so that is its primary language and it is genuinely PARTIAL —
    # marking it READY would promise a Chinese version that does not exist
    # and never will without re-running the model. The frontend falls back
    # to whichever language is present, so these keep rendering unchanged.
    op.execute("UPDATE inner_readings SET primary_language = 'en' WHERE primary_language IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("inner_readings", "generation_status")
    op.drop_column("inner_readings", "primary_language")
    for name, _ in reversed(_ZH_COLUMNS):
        op.drop_column("inner_readings", name)
