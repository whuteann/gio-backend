"""Add lumenart_products cache table.

Backs the lazy, 24h-stale-check refresh of LumenArt's Shopify catalog —
see app/services/lumenart.py. Feeds the recommendation engine's phone case
pick (app/services/recommendation.py), replacing the empty
app/services/phonecase_api.py placeholder (now removed).
"""
from alembic import op
import sqlalchemy as sa

revision = "5b95d6775327"
down_revision = "f21d9c8e7012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lumenart_products",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("handle", sa.String(), nullable=False),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_lumenart_products_fetched_at", "lumenart_products", ["fetched_at"])


def downgrade():
    op.drop_index("ix_lumenart_products_fetched_at", table_name="lumenart_products")
    op.drop_table("lumenart_products")
