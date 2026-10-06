from sqlalchemy import Column, DateTime, Numeric, String
from sqlalchemy.sql import func

from app.database import Base


class LumenartProduct(Base):
    """A lazy-refreshed cache of LumenArt's Shopify catalog — see
    app/services/lumenart.py. `id` is Shopify's own GID (e.g.
    "gid://shopify/Product/..."), so a refresh can simply upsert rather than
    needing a separate mapping table. `fetched_at` is shared across one
    whole refresh batch, not per-row — see lumenart.py's staleness check.
    """

    __tablename__ = "lumenart_products"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    handle = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    price = Column(Numeric(10, 2), nullable=True)
    currency = Column(String, nullable=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
