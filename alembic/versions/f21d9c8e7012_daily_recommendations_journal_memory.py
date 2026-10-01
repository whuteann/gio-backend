"""Daily bilingual recommendations and journal narrative memory.

Preserves historical profiles and content; old profiles have no daily key.
"""
from alembic import op
import sqlalchemy as sa

revision = "f21d9c8e7012"
down_revision = "d3f19b4ea0f9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("narrative_entries", sa.Column("journal_entry_id", sa.UUID(), nullable=True))
    op.create_foreign_key("narrative_entries_journal_entry_id_fkey", "narrative_entries", "journal_entries", ["journal_entry_id"], ["id"], ondelete="CASCADE")
    op.drop_constraint("ck_narrative_entry_single_source", "narrative_entries", type_="check")
    op.create_check_constraint("ck_narrative_entry_single_source", "narrative_entries", "(check_in_session_id IS NOT NULL)::int + (inner_reading_id IS NOT NULL)::int + (journal_entry_id IS NOT NULL)::int = 1")
    op.add_column("recommendation_profiles", sa.Column("recommendation_date", sa.Date(), nullable=True))
    op.add_column("recommendation_profiles", sa.Column("current_focus_zh", sa.String(), nullable=True))
    op.add_column("recommendation_profiles", sa.Column("summary_zh", sa.String(), nullable=True))
    op.create_unique_constraint("uq_recommendation_user_day", "recommendation_profiles", ["user_id", "recommendation_date"])
    for name in ("title_zh", "reason_zh"):
        op.add_column("recommendation_items", sa.Column(name, sa.String(), nullable=True))
    op.add_column("recommendation_items", sa.Column("currency", sa.String(), nullable=False, server_default="MYR"))


def downgrade():
    # A journal memory cannot satisfy the old two-source constraint. Refuse
    # rather than silently deleting the user's accumulated memory.
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM narrative_entries WHERE journal_entry_id IS NOT NULL)")).scalar():
        raise RuntimeError("Journal memory exists; archive it explicitly before downgrading.")
    op.drop_constraint("ck_narrative_entry_single_source", "narrative_entries", type_="check")
    op.create_check_constraint("ck_narrative_entry_single_source", "narrative_entries", "(check_in_session_id IS NOT NULL)::int + (inner_reading_id IS NOT NULL)::int = 1")
    op.drop_column("narrative_entries", "journal_entry_id")
    op.drop_constraint("uq_recommendation_user_day", "recommendation_profiles", type_="unique")
    for name in ("recommendation_date", "current_focus_zh", "summary_zh"):
        op.drop_column("recommendation_profiles", name)
    for name in ("title_zh", "reason_zh", "currency"):
        op.drop_column("recommendation_items", name)
