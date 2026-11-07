"""Explicit artwork colours, never inferred from a product name by the AI.

Shopify owners can set custom.auren_colour_keys (list.single_line_text_field)
to the Auren keys below. Until then, the small reviewed catalogue below is
bound to the exact image version inspected on 2026-11-07. A changed image
needs a new review; accents, pink, purple and orange are not silently treated
as red, brown or gold. See docs/phone_case_colour_matching.md.
"""
import json

COLOUR_KEYS = frozenset({"scarlet", "russet", "gold", "forest", "ocean"})

_REVIEWED_ARTWORK = {
    "gid://shopify/Product/10114644869417": (
        "https://cdn.shopify.com/s/files/1/0963/9254/4553/files/136A24EA-2509-45A5-B479-634578E51531.png?v=1783130563", "ocean"),
    "gid://shopify/Product/10114653389097": (
        "https://cdn.shopify.com/s/files/1/0963/9254/4553/files/D58CA820-8E11-493B-89FA-5E76829FC9E2.png?v=1783131603", "forest"),
    "gid://shopify/Product/10114691727657": (
        "https://cdn.shopify.com/s/files/1/0963/9254/4553/files/IMG-0094.png?v=1783151710", "forest"),
}


def product_colour_keys(raw: dict) -> list[str]:
    """An explicit merchant value takes precedence, including [] to exclude.

    Malformed or unknown values fail closed rather than widening the pool.
    Standard shopify.color-pattern references are currently unreadable by
    this installation and are not guessed from opaque metaobject IDs.
    """
    explicit = raw.get("aurenColours")
    if explicit is not None:
        if explicit.get("type") != "list.single_line_text_field":
            return []
        try:
            values = json.loads(explicit.get("value", ""))
        except (ValueError, TypeError):
            return []
        if not isinstance(values, list) or not all(isinstance(v, str) and v in COLOUR_KEYS for v in values):
            return []
        return sorted(set(values))
    review = _REVIEWED_ARTWORK.get(raw.get("id"))
    image = ((raw.get("featuredMedia") or {}).get("image") or {}).get("url")
    return [review[1]] if review and image == review[0] else []


def matching_cases(candidates: list[dict], colour_key: str) -> list[dict]:
    if colour_key not in COLOUR_KEYS:
        return []
    return [c for c in candidates if colour_key in (c.get("colour_keys") or [])]
