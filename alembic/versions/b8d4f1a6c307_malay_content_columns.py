"""malay content columns

Revision ID: b8d4f1a6c307
Revises: e4a71c9b2d05
Create Date: 2026-11-06 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b8d4f1a6c307'
down_revision: Union[str, Sequence[str], None] = 'e4a71c9b2d05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# One `_ms` sibling per existing `_zh` column. All nullable and all left
# NULL — there is deliberately no backfill (MALAY_LANGUAGE_PLAN.md): existing
# rows stay English-only forever and the frontend falls back to them. Only
# content generated after this ships is trilingual.
_TEXT = sa.String()
_JSON = postgresql.JSONB()

_COLUMNS: list[tuple[str, str, object]] = [
    ("check_in_sessions", "title_ms", _TEXT),
    ("check_in_sessions", "subtitle_ms", _TEXT),

    ("core_personalities", "title_ms", _TEXT),
    ("core_personalities", "subtitle_ms", _TEXT),
    ("core_personalities", "overview_ms", _TEXT),
    ("core_personalities", "summary_ms", _TEXT),
    ("core_personalities", "birthday_number_points_ms", _JSON),
    ("core_personalities", "life_path_number_points_ms", _JSON),
    ("core_personalities", "talent_number_points_ms", _JSON),

    ("inner_readings", "title_ms", _TEXT),
    ("inner_readings", "subtitle_ms", _TEXT),
    ("inner_readings", "narrative_ms", _TEXT),
    ("inner_readings", "insight_ms", _TEXT),
    ("inner_readings", "reflection_question_ms", _TEXT),
    ("inner_readings", "result_summary_ms", _TEXT),
    ("inner_readings", "current_focus_ms", _TEXT),
    ("inner_readings", "life_area_insights_ms", _JSON),

    ("inner_state_snapshots", "summary_ms", _TEXT),

    ("recommendation_profiles", "current_focus_ms", _TEXT),
    ("recommendation_profiles", "summary_ms", _TEXT),
    ("recommendation_profiles", "letter_ms", _TEXT),

    ("recommendation_items", "title_ms", _TEXT),
    ("recommendation_items", "reason_ms", _TEXT),
]

# `generation_status` is two-state (PARTIAL/READY) and cannot say *which*
# languages landed. With two background passes instead of one, a client
# needs to tell "Malay still generating" from "Malay failed and never
# will" — hence an explicit list. generation_status is kept and now means
# "every supported language is present".
_READY_TABLES = ("inner_readings", "core_personalities")


def upgrade() -> None:
    """Upgrade schema."""
    for table, name, type_ in _COLUMNS:
        op.add_column(table, sa.Column(name, type_, nullable=True))
    for table in _READY_TABLES:
        op.add_column(table, sa.Column("languages_ready", postgresql.JSONB(), nullable=True))
        # Existing rows: whatever they already have. primary_language is
        # non-null on every row after migration c7f2b9a04d31 backfilled it,
        # and a row marked READY also has its second language.
        op.execute(f"""
            UPDATE {table}
            SET languages_ready = CASE
                WHEN generation_status = 'READY' THEN '["en", "zh"]'::jsonb
                ELSE to_jsonb(ARRAY[COALESCE(primary_language, 'en')])
            END
            WHERE languages_ready IS NULL
        """)
        # Nothing is complete any more: three languages are supported and no
        # existing row has Malay. Leaving stale READY rows would tell the UI
        # a Malay version exists.
        op.execute(f"UPDATE {table} SET generation_status = 'PARTIAL'")


def downgrade() -> None:
    """Downgrade schema."""
    for table in _READY_TABLES:
        op.drop_column(table, "languages_ready")
    for table, name, _ in reversed(_COLUMNS):
        op.drop_column(table, name)
