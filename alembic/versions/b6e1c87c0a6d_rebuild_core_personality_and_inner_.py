"""rebuild core_personality and inner_state_snapshot

Revision ID: b6e1c87c0a6d
Revises: ee09635a3ec5
Create Date: 2026-09-23 00:00:00.000000

Realigns both tables to what docs/behaviour_log_0001.md and
docs/behaviour_log_0002.md describe (see plan approved during review):
Core Personality's old archetype-quiz shape and Inner State's old
"balance"-bearing shape are replaced, not extended. Destructive — dropping
and recreating both tables outright rather than column-by-column
alter/drop, since every account in this environment is demo data.

recommendation_profiles FKs into both tables (core_personality_id,
state_snapshot_id), so it (and its child recommendation_items) has to be
dropped first and recreated after — unchanged shape, just re-pointed at the
freshly recreated tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b6e1c87c0a6d'
down_revision: Union[str, Sequence[str], None] = 'ee09635a3ec5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_recommendation_tables() -> None:
    op.create_table(
        'recommendation_profiles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('state_snapshot_id', sa.UUID(), nullable=False),
        sa.Column('core_personality_id', sa.UUID(), nullable=False),
        sa.Column('trigger_type', sa.String(), nullable=False),
        sa.Column('trigger_check_in_session_id', sa.UUID(), nullable=True),
        sa.Column('trigger_inner_reading_id', sa.UUID(), nullable=True),
        sa.Column('current_focus', sa.String(), nullable=False),
        sa.Column('summary', sa.String(), nullable=False),
        sa.Column('colour_key', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            '(trigger_check_in_session_id IS NOT NULL)::int + (trigger_inner_reading_id IS NOT NULL)::int = 1',
            name='ck_recommendation_single_trigger',
        ),
        sa.ForeignKeyConstraint(['core_personality_id'], ['core_personalities.id']),
        sa.ForeignKeyConstraint(['state_snapshot_id'], ['inner_state_snapshots.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trigger_check_in_session_id'], ['check_in_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['trigger_inner_reading_id'], ['inner_readings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_recommendation_profiles_generated_at'), 'recommendation_profiles', ['generated_at'], unique=False)
    op.create_index(op.f('ix_recommendation_profiles_user_id'), 'recommendation_profiles', ['user_id'], unique=False)

    op.create_table(
        'recommendation_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('recommendation_profile_id', sa.UUID(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('reference_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('rank', sa.SmallInteger(), nullable=False),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('destination_url', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['recommendation_profile_id'], ['recommendation_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_recommendation_items_recommendation_profile_id'), 'recommendation_items', ['recommendation_profile_id'], unique=False)


def _drop_recommendation_tables() -> None:
    op.drop_index(op.f('ix_recommendation_items_recommendation_profile_id'), table_name='recommendation_items')
    op.drop_table('recommendation_items')
    op.drop_index(op.f('ix_recommendation_profiles_user_id'), table_name='recommendation_profiles')
    op.drop_index(op.f('ix_recommendation_profiles_generated_at'), table_name='recommendation_profiles')
    op.drop_table('recommendation_profiles')


def upgrade() -> None:
    """Upgrade schema."""
    _drop_recommendation_tables()

    op.drop_table('core_personalities')
    op.create_table(
        'core_personalities',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('subtitle', sa.String(), nullable=True),
        sa.Column('overview', sa.String(), nullable=True),
        sa.Column('birthday_number', sa.Integer(), nullable=True),
        sa.Column('birthday_number_content', sa.String(), nullable=True),
        sa.Column('life_path_number', sa.Integer(), nullable=True),
        sa.Column('life_path_number_content', sa.String(), nullable=True),
        sa.Column('talent_number', sa.String(), nullable=True),
        sa.Column('talent_number_content', sa.String(), nullable=True),
        sa.Column('scarlet_score', sa.SmallInteger(), nullable=True),
        sa.Column('russet_score', sa.SmallInteger(), nullable=True),
        sa.Column('gold_score', sa.SmallInteger(), nullable=True),
        sa.Column('forest_score', sa.SmallInteger(), nullable=True),
        sa.Column('ocean_score', sa.SmallInteger(), nullable=True),
        sa.Column('summary', sa.String(), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )

    op.drop_table('inner_state_snapshots')
    op.create_table(
        'inner_state_snapshots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('source_type', sa.String(), nullable=False),
        sa.Column('check_in_session_id', sa.UUID(), nullable=True),
        sa.Column('inner_reading_id', sa.UUID(), nullable=True),
        sa.Column('emotional_energy', sa.SmallInteger(), nullable=False),
        sa.Column('mental_clarity', sa.SmallInteger(), nullable=False),
        sa.Column('inner_pressure', sa.SmallInteger(), nullable=False),
        sa.Column('grounding', sa.SmallInteger(), nullable=False),
        sa.Column('colour_key', sa.String(), nullable=True),
        sa.Column('insight', sa.String(), nullable=True),
        sa.Column('reflection_question', sa.String(), nullable=True),
        sa.Column('reminder', sa.String(), nullable=True),
        sa.Column('current_focus', sa.String(), nullable=False),
        sa.Column('friendly_advice', sa.String(), nullable=True),
        sa.Column('affirmation', sa.String(), nullable=True),
        sa.Column('summary', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            '(check_in_session_id IS NOT NULL)::int + (inner_reading_id IS NOT NULL)::int = 1',
            name='ck_inner_state_snapshot_single_source',
        ),
        sa.ForeignKeyConstraint(['check_in_session_id'], ['check_in_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['inner_reading_id'], ['inner_readings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_inner_state_snapshots_created_at'), 'inner_state_snapshots', ['created_at'], unique=False)
    op.create_index(op.f('ix_inner_state_snapshots_user_id'), 'inner_state_snapshots', ['user_id'], unique=False)

    _create_recommendation_tables()


def downgrade() -> None:
    """Downgrade schema."""
    _drop_recommendation_tables()

    op.drop_index(op.f('ix_inner_state_snapshots_user_id'), table_name='inner_state_snapshots')
    op.drop_index(op.f('ix_inner_state_snapshots_created_at'), table_name='inner_state_snapshots')
    op.drop_table('inner_state_snapshots')

    op.create_table(
        'inner_state_snapshots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('source_type', sa.String(), nullable=False),
        sa.Column('check_in_session_id', sa.UUID(), nullable=True),
        sa.Column('inner_reading_id', sa.UUID(), nullable=True),
        sa.Column('emotional_energy', sa.SmallInteger(), nullable=False),
        sa.Column('mental_clarity', sa.SmallInteger(), nullable=False),
        sa.Column('inner_pressure', sa.SmallInteger(), nullable=False),
        sa.Column('grounding', sa.SmallInteger(), nullable=False),
        sa.Column('balance', sa.SmallInteger(), nullable=False),
        sa.Column('current_focus', sa.String(), nullable=False),
        sa.Column('summary', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            '(check_in_session_id IS NOT NULL)::int + (inner_reading_id IS NOT NULL)::int = 1',
            name='ck_inner_state_snapshot_single_source',
        ),
        sa.ForeignKeyConstraint(['check_in_session_id'], ['check_in_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['inner_reading_id'], ['inner_readings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_inner_state_snapshots_created_at'), 'inner_state_snapshots', ['created_at'], unique=False)
    op.create_index(op.f('ix_inner_state_snapshots_user_id'), 'inner_state_snapshots', ['user_id'], unique=False)

    op.drop_table('core_personalities')
    op.create_table(
        'core_personalities',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('archetype', sa.String(), nullable=False),
        sa.Column('icon', sa.String(), nullable=False),
        sa.Column('thinking', sa.SmallInteger(), nullable=False),
        sa.Column('emotional_sensitivity', sa.SmallInteger(), nullable=False),
        sa.Column('adaptability', sa.SmallInteger(), nullable=False),
        sa.Column('willpower', sa.SmallInteger(), nullable=False),
        sa.Column('overall_explanation', sa.String(), nullable=False),
        sa.Column('pillar_explanations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('assessment_version', sa.String(), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('recalibrated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_core_personalities_user_id'), 'core_personalities', ['user_id'], unique=False)

    _create_recommendation_tables()
