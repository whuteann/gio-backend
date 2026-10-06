"""LumenArt (Shopify) phone-case catalog — a lazy, 24h-cached vendor source
feeding the recommendation engine's phone case pick (see
app/services/recommendation.py and "LumenArt-APi Integration.md" at the
platform root for the full API contract this mirrors).

Lazy-on-read, not scheduled: every call checks the cache's age and only
hits Shopify when it's missing or >24h stale — no new scheduler/cron
infra, same philosophy as app/services/product_api.py. A Shopify failure
during a stale refresh falls back to serving whatever's already cached,
even if stale, rather than returning nothing — recommendation generation
must never depend on this vendor's uptime, same principle as the rest of
this best-effort vendor layer.

Runs fully synchronously (plain httpx.Client, not AsyncClient) because its
one caller, app/services/recommendation.py, reaches it from inside a sync
SQLAlchemy session — not worth bridging into the async stone-product half
for an 8-product catalog.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.lumenart import LumenartProduct

logger = logging.getLogger(__name__)

_CACHE_TTL = timedelta(hours=24)
_TOKEN_URL_TMPL = "https://{domain}/admin/oauth/access_token"
_GRAPHQL_URL_TMPL = "https://{domain}/admin/api/2026-10/graphql.json"
_TIMEOUT_SECONDS = 10.0

_PRODUCTS_QUERY = """
query GetProducts($after: String) {
  products(first: 100, after: $after, sortKey: ID) {
    nodes {
      id
      title
      handle
      status
      featuredMedia {
        ... on MediaImage {
          image { url }
        }
      }
      priceRangeV2 {
        minVariantPrice { amount currencyCode }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

# In-process token cache — tokens last ~24h per the integration doc;
# re-fetched a minute early rather than cutting it exactly at expiry. Per
# worker process (fine: worst case each worker fetches its own once).
_cached_token: str | None = None
_cached_token_expires_at: datetime | None = None


def _parse_decimal(raw) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None


def _get_access_token(client: httpx.Client) -> str | None:
    global _cached_token, _cached_token_expires_at
    now = datetime.now(timezone.utc)
    if _cached_token and _cached_token_expires_at and now < _cached_token_expires_at:
        return _cached_token

    if not settings.lumenart_client_secret:
        logger.warning("LumenArt client secret not configured — skipping phone case refresh.")
        return None

    try:
        response = client.post(
            _TOKEN_URL_TMPL.format(domain=settings.lumenart_shop_domain),
            data={
                "grant_type": "client_credentials",
                "client_id": settings.lumenart_client_id,
                "client_secret": settings.lumenart_client_secret,
            },
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("LumenArt token request failed.", exc_info=True)
        return None

    token = payload.get("access_token")
    if not token:
        return None
    expires_in = payload.get("expires_in")
    _cached_token = token
    _cached_token_expires_at = now + timedelta(seconds=int(expires_in) - 60) if expires_in else now + timedelta(hours=23)
    return token


def _fetch_all_products(client: httpx.Client, token: str) -> list[dict]:
    url = _GRAPHQL_URL_TMPL.format(domain=settings.lumenart_shop_domain)
    headers = {"Content-Type": "application/json", "X-Shopify-Access-Token": token}
    products: list[dict] = []
    after = None
    for _ in range(20):  # hard stop — this catalog is 8 products, real pagination never expected
        response = client.post(url, headers=headers, json={"query": _PRODUCTS_QUERY, "variables": {"after": after}})
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            logger.warning("LumenArt GraphQL returned errors: %s", payload["errors"])
            break
        data = (payload.get("data") or {}).get("products") or {}
        products.extend(data.get("nodes") or [])
        page_info = data.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
    return products


def _refresh_cache(db: Session) -> None:
    with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
        token = _get_access_token(client)
        if not token:
            return
        try:
            raw_products = _fetch_all_products(client, token)
        except (httpx.HTTPError, ValueError):
            logger.warning("LumenArt product fetch failed — keeping existing cache.", exc_info=True)
            return

    now = datetime.now(timezone.utc)
    # Replace wholesale rather than diff/upsert — an 8-product catalog makes
    # that unnecessary complexity. Not committed here: this runs inside the
    # caller's existing request-scoped session/transaction (see
    # recommendation.py) — only the route handler commits.
    db.query(LumenartProduct).delete()
    for raw in raw_products:
        if raw.get("status") != "ACTIVE":
            continue
        image = (raw.get("featuredMedia") or {}).get("image") or {}
        min_price = (raw.get("priceRangeV2") or {}).get("minVariantPrice") or {}
        db.add(LumenartProduct(
            id=raw["id"],
            title=raw.get("title") or "LumenArt phone case",
            handle=raw.get("handle") or "",
            image_url=image.get("url"),
            price=_parse_decimal(min_price.get("amount")),
            currency=min_price.get("currencyCode"),
            fetched_at=now,
        ))
    db.flush()


def get_phone_case_candidates(db: Session) -> list[dict]:
    """The one entry point app/services/recommendation.py calls. Refreshes
    the cache first if it's missing or >24h stale; a failed refresh falls
    through to whatever's already cached (even if stale) rather than
    returning nothing and losing a day of phone case picks to a transient
    vendor blip. Returns dicts shaped like app/services/product_api.py's
    candidates — `name`/`price`/`currency`/`primary_image`/`handle` —
    which is what app/services/ai_recommendation.py and
    recommendation.py::_phone_case_item already expect."""
    newest = db.query(LumenartProduct.fetched_at).order_by(LumenartProduct.fetched_at.desc()).first()
    is_stale = newest is None or (datetime.now(timezone.utc) - newest[0]) > _CACHE_TTL
    if is_stale:
        try:
            _refresh_cache(db)
        except Exception:
            logger.exception("LumenArt cache refresh failed unexpectedly — serving existing cache.")

    rows = db.query(LumenartProduct).all()
    return [
        {
            "id": row.id,
            "handle": row.handle,
            "name": row.title,
            "primary_image": row.image_url,
            "price": str(row.price) if row.price is not None else None,
            "currency": row.currency or "MYR",
        }
        for row in rows
    ]
