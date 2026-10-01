"""Client for the third-party product-filter API — see
third-party-product-filter-api/README.md for the full contract (this repo
copy has no credentials or backend source, just the read contract). Plain
HTTPS GET, no auth.

Best-effort by design: check-in/Inner Reading submission (XP, streak,
badges, the snapshot itself) must never depend on this vendor's uptime, so
any failure — timeout, non-2xx, unexpected shape — degrades to an empty
list rather than raising. `build_recommendation` treats an empty list as
"no product recommendations this time," not an error.
"""

import httpx

_FILTER_URL = "https://api.giobyquartzic.com/api/v1/products/filter"
_TIMEOUT_SECONDS = 5.0
_PER_PAGE = 10


async def fetch_products_by_colour(colour_key: str) -> list[dict]:
    """`colour_key` is one of our own 5 colour keys (scarlet/russet/gold/
    forest/ocean) — they match the API's `elements` values exactly."""
    params = {"elements": colour_key, "is_active": "true", "per_page": _PER_PAGE, "page": 1, "currency": "MYR"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(_FILTER_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return []
    data = payload.get("data")
    return data if isinstance(data, list) else []
