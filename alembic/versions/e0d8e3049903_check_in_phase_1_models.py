"""check-in Phase 1 models (behaviour_log_0006)

Revision ID: e0d8e3049903
Revises: 8a653b4ba614
Create Date: 2026-09-24 00:00:00.000000

Four changes, per docs/behaviour_log_0006.md Phase 1:
- check_in_question_sets: date-only uniqueness -> composite (date, increment)
- users: last_check_in_at / check_in_count_today (drives the increment)
- check_in_sessions: narrative_entry_id (nullable, SET NULL) back to the
  NarrativeEntry generated for that check-in
- inner_state_snapshots: the six narrative fields become one JSONB column
  each (holding {"en":..., "zh":...}) instead of an _en/_zh String pair —
  confirmed during review; summary_en/summary_zh are NOT part of this
  (different field, stays as-is).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e0d8e3049903'
down_revision: Union[str, Sequence[str], None] = '8a653b4ba614'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NARRATIVE_FIELDS = ["insight", "reflection_question", "reminder", "current_focus", "friendly_advice", "affirmation"]


def upgrade() -> None:
    """Upgrade schema."""
    # --- check_in_question_sets: date -> (date, increment) ---
    op.add_column('check_in_question_sets', sa.Column('increment', sa.Integer(), nullable=True))
    op.execute("UPDATE check_in_question_sets SET increment = 1 WHERE increment IS NULL")
    op.alter_column('check_in_question_sets', 'increment', nullable=False)
    op.drop_index('ix_check_in_question_sets_date', table_name='check_in_question_sets')
    op.create_index('ix_check_in_question_sets_date', 'check_in_question_sets', ['date'], unique=False)
    op.create_unique_constraint(
        'uq_check_in_question_set_date_increment', 'check_in_question_sets', ['date', 'increment'],
    )

    # --- users: check-in tracking ---
    op.add_column('users', sa.Column('last_check_in_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('check_in_count_today', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('users', 'check_in_count_today', server_default=None)

    # --- check_in_sessions: link to the NarrativeEntry it produced ---
    op.add_column('check_in_sessions', sa.Column('narrative_entry_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'check_in_sessions_narrative_entry_id_fkey', 'check_in_sessions', 'narrative_entries',
        ['narrative_entry_id'], ['id'], ondelete='SET NULL',
    )

    # --- inner_state_snapshots: 12 bilingual String columns -> 6 JSONB ---
    for field in NARRATIVE_FIELDS:
        op.drop_column('inner_state_snapshots', f'{field}_en')
        op.drop_column('inner_state_snapshots', f'{field}_zh')
        op.add_column('inner_state_snapshots', sa.Column(field, postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    for field in NARRATIVE_FIELDS:
        op.drop_column('inner_state_snapshots', field)
        op.add_column('inner_state_snapshots', sa.Column(f'{field}_en', sa.String(), nullable=True))
        op.add_column('inner_state_snapshots', sa.Column(f'{field}_zh', sa.String(), nullable=True))

    op.drop_constraint('check_in_sessions_narrative_entry_id_fkey', 'check_in_sessions', type_='foreignkey')
    op.drop_column('check_in_sessions', 'narrative_entry_id')

    op.drop_column('users', 'check_in_count_today')
    op.drop_column('users', 'last_check_in_at')

    op.drop_constraint('uq_check_in_question_set_date_increment', 'check_in_question_sets', type_='unique')
    op.drop_index('ix_check_in_question_sets_date', table_name='check_in_question_sets')
    op.create_index('ix_check_in_question_sets_date', 'check_in_question_sets', ['date'], unique=True)
    op.drop_column('check_in_question_sets', 'increment')
