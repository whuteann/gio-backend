"""Colour-first phone case catalogue and per-profile selection state."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e308ca517b42"
down_revision = "d706da913b21"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("lumenart_products", sa.Column("colour_keys", postgresql.JSONB(), nullable=True))
    op.add_column("lumenart_products", sa.Column("design_description", sa.String(), nullable=True))
    op.add_column("recommendation_profiles", sa.Column("phone_case_colour_key", sa.String(), nullable=True))
    op.add_column("recommendation_profiles", sa.Column("phone_case_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("recommendation_profiles", sa.Column("phone_case_status", sa.String(), nullable=True))


def downgrade():
    for name in ("phone_case_status", "phone_case_checked_at", "phone_case_colour_key"):
        op.drop_column("recommendation_profiles", name)
    op.drop_column("lumenart_products", "design_description")
    op.drop_column("lumenart_products", "colour_keys")
