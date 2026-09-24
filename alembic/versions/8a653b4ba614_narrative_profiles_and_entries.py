"""narrative profiles and entries

Revision ID: 8a653b4ba614
Revises: e0584db7d132
Create Date: 2026-09-24 00:00:00.000000

New tables only — Narrative's system-memory model (see
docs/behaviour_log_0005.md). Purely additive, nothing existing touched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8a653b4ba614'
down_revision: Union[str, Sequence[str], None] = 'e0584db7d132'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'narrative_profiles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )

    op.create_table(
        'narrative_entries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('narrative_profile_id', sa.UUID(), nullable=False),
        sa.Column('source_type', sa.String(), nullable=False),
        sa.Column('check_in_session_id', sa.UUID(), nullable=True),
        sa.Column('inner_reading_id', sa.UUID(), nullable=True),
        sa.Column('summary', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            '(check_in_session_id IS NOT NULL)::int + (inner_reading_id IS NOT NULL)::int = 1',
            name='ck_narrative_entry_single_source',
        ),
        sa.ForeignKeyConstraint(['check_in_session_id'], ['check_in_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['inner_reading_id'], ['inner_readings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['narrative_profile_id'], ['narrative_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_narrative_entries_profile_created', 'narrative_entries',
        ['narrative_profile_id', sa.text('created_at DESC')], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_narrative_entries_profile_created', table_name='narrative_entries')
    op.drop_table('narrative_entries')
    op.drop_table('narrative_profiles')
