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

import re

import httpx

_FILTER_URL = "https://api.giobyquartzic.com/api/v1/products/filter"
_TIMEOUT_SECONDS = 5.0
_PER_PAGE = 10

_CJK_RE = re.compile(r"[一-鿿]")


def _has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def _split_bilingual(text: str) -> tuple[str, str]:
    """Best-effort zh/en split of one vendor-supplied bilingual string.
    Confirmed messy across the live catalog: the separator is sometimes
    "|" and sometimes the full-width "｜", language order flips (zh-first
    on some products, en-first on others), and a trailing "<|> ..."
    segment (usually empty, sometimes a duplicate) follows on some rows
    but not others. Detects which half is actually Chinese by character
    set rather than trusting position, since position isn't reliable."""
    primary = text.split("<|>")[0].strip()
    for sep in ("|", "｜"):
        if sep in primary:
            parts = [p.strip() for p in primary.split(sep, 1)]
            if len(parts) == 2 and parts[0] and parts[1]:
                return (parts[0], parts[1]) if _has_cjk(parts[0]) else (parts[1], parts[0])
    return primary, primary


def parse_specifications(raw: dict | None) -> list[dict]:
    """Vendor `specifications` -> a clean, already zh/en-split list, e.g.
    [{"label_en": "Materials", "label_zh": "材质", "value_en": "...",
    "value_zh": "..."}, ...]. Rows with an empty value are dropped."""
    if not raw:
        return []
    result = []
    for key, value in raw.items():
        text_value = str(value).strip() if value is not None else ""
        if not text_value:
            continue
        label_zh, label_en = _split_bilingual(str(key))
        value_zh, value_en = _split_bilingual(text_value)
        if not value_zh and not value_en:
            continue
        result.append({"label_en": label_en, "label_zh": label_zh, "value_en": value_en, "value_zh": value_zh})
    return result


async def fetch_products(colour_key: str, stone_type: str | None = None) -> list[dict]:
    """`colour_key` is one of our own 5 colour keys (scarlet/russet/gold/
    forest/ocean) — they match the API's `elements` values exactly.
    `stone_type` is one of FOCUS_TO_MATERIAL's values (Crystal/Nephrite/
    Jade) — the vendor's `type` filter does a case-insensitive partial
    match, confirmed against the live API, so these pass straight through."""
    params = {"elements": colour_key, "is_active": "true", "per_page": _PER_PAGE, "page": 1, "currency": "MYR"}
    if stone_type:
        params["type"] = stone_type
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(_FILTER_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return []
    data = payload.get("data")
    return data if isinstance(data, list) else []
