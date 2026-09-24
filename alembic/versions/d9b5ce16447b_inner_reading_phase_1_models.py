"""inner_reading_phase_1_models

Revision ID: d9b5ce16447b
Revises: 28313880ed51
Create Date: 2026-09-23 13:06:26.730234

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd9b5ce16447b'
down_revision: Union[str, Sequence[str], None] = '28313880ed51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('last_inner_reading_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('inner_reading_count_today', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('users', 'inner_reading_count_today', server_default=None)

    # Existing rows are the old static-demo question sets, keyed by a
    # scheme this migration removes entirely (global `ordinal`, no daily
    # reset) — nothing worth preserving, see docs/behaviour_log_0007.md.
    op.execute('DELETE FROM inner_reading_question_sets')
    op.drop_index('ix_inner_reading_question_sets_ordinal', table_name='inner_reading_question_sets')
    op.drop_column('inner_reading_question_sets', 'ordinal')
    op.add_column('inner_reading_question_sets', sa.Column('date', sa.Date(), nullable=False))
    op.add_column('inner_reading_question_sets', sa.Column('increment', sa.Integer(), nullable=False))
    op.create_index('ix_inner_reading_question_sets_date', 'inner_reading_question_sets', ['date'])
    op.create_unique_constraint(
        'uq_inner_reading_question_set_date_increment', 'inner_reading_question_sets', ['date', 'increment']
    )

    op.add_column('inner_readings', sa.Column('life_area_insights', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('inner_readings', sa.Column('narrative_entry_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'inner_readings_narrative_entry_id_fkey', 'inner_readings', 'narrative_entries',
        ['narrative_entry_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('inner_readings_narrative_entry_id_fkey', 'inner_readings', type_='foreignkey')
    op.drop_column('inner_readings', 'narrative_entry_id')
    op.drop_column('inner_readings', 'life_area_insights')

    op.drop_constraint('uq_inner_reading_question_set_date_increment', 'inner_reading_question_sets', type_='unique')
    op.drop_index('ix_inner_reading_question_sets_date', table_name='inner_reading_question_sets')
    op.drop_column('inner_reading_question_sets', 'increment')
    op.drop_column('inner_reading_question_sets', 'date')
    op.add_column('inner_reading_question_sets', sa.Column('ordinal', sa.Integer(), nullable=False, server_default='1'))
    op.alter_column('inner_reading_question_sets', 'ordinal', server_default=None)
    op.create_index('ix_inner_reading_question_sets_ordinal', 'inner_reading_question_sets', ['ordinal'], unique=True)

    op.drop_column('users', 'inner_reading_count_today')
    op.drop_column('users', 'last_inner_reading_at')
