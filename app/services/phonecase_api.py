"""Phone case candidates for the recommendation engine's "at least 1 phone
case" pick (see app/services/ai_recommendation.py).

PLACEHOLDER — confirmed via the live vendor API (2026-10) that
api.giobyquartzic.com/products/filter has no phone-case inventory at all:
the entire catalog is Crystal/Nephrite/Jade stone products, nothing else.
This reuses that same endpoint with a `type` guess that doesn't match
anything yet, so it degrades to a clean empty list today (not an error) —
best-effort, same as app/services/product_api.py. Revisit once a real
phone-case source (this same vendor adding inventory, or a different
endpoint entirely) exists: swap _FILTER_URL/_PLACEHOLDER_TYPE below, or
point this at the new source directly.
"""

import httpx

_FILTER_URL = "https://api.giobyquartzic.com/api/v1/products/filter"
_PLACEHOLDER_TYPE = "phone_case"
_TIMEOUT_SECONDS = 5.0
_PER_PAGE = 6


async def fetch_phone_cases() -> list[dict]:
    params = {"type": _PLACEHOLDER_TYPE, "is_active": "true", "per_page": _PER_PAGE, "page": 1, "currency": "MYR"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(_FILTER_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return []
    data = payload.get("data")
    return data if isinstance(data, list) else []
