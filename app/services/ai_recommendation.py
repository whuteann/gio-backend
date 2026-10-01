"""AI product picker — selects which of the live, colour-filtered
candidate products (app/services/product_api.py) to actually recommend.
See docs/behaviour_log_0012.md.

Same "constrained selection" mechanism as AffirmationId/InsightId/
ReflectionQuestionId (app/schemas/ai_outcome.py), but the candidate set
isn't a fixed catalog known at import time — it's whatever the vendor API
returned this call. So the Enum (and the model wrapping it) is built fresh
per call from the actual fetched ids, using safe positional keys ("P01",
"P02", ...) rather than the vendor's raw UUIDs, which aren't valid Python
identifiers. The model is structurally incapable of returning a key that
wasn't really in this call's candidate list.

Unlike the older free-generated Inner State fields (still English-only,
see ai_outcome.py), this is a brand-new call, so it writes `reason_en` and
`reason_zh` directly in the same structured response — genuinely bilingual
from the start.
"""

from enum import Enum

from openai import AsyncOpenAI
from pydantic import BaseModel, create_model

from app.config import settings

_client = AsyncOpenAI(api_key=settings.openai_api_key)

# A devoted-letter-writer persona — someone who puts another person's
# feelings into words the way a trusted scribe writes on their behalf, so
# `reason` reads as a line lifted from a real letter rather than product
# copy. Described directly here rather than naming its inspiration, so the
# voice stays controllable instead of imitating a specific character.
_SYSTEM_MESSAGE = (
    "You are a devoted letter-writer for a wellness app called Auren — someone who "
    "writes short, sincere letters carrying another person's feelings into words. "
    "You must strictly follow the required JSON structure."
)


def _candidate_key(index: int) -> str:
    return f"P{index + 1:02d}"


def _build_schema(candidate_keys: list[str]) -> type[BaseModel]:
    ProductKey = Enum("ProductKey", {k: k for k in candidate_keys})
    Pick = create_model(
        "ProductPick",
        product_key=(ProductKey, ...),
        material_tag=(str, ...),
        reason_en=(str, ...),
        reason_zh=(str, ...),
    )
    return create_model("ProductPicks", picks=(list[Pick], ...))


def _guess_material(name: str | None) -> str:
    """Fallback-path material guess — no AI call. Vendor product names are
    bilingual, "中文 | ENGLISH" (see docs/behaviour_log_0012.md); the English
    half, title-cased, is as close to a clean material name as the raw data
    gets without a model call."""
    if not name:
        return "Crystal"
    english = name.split("|")[-1].strip()
    return english.title() if english else "Crystal"


async def pick_products(
    *,
    narrative_prompt: str,
    candidates: list[dict],
    limit: int,
) -> list[dict]:
    """Returns up to `limit` of `candidates`, each with `reason_en`/
    `reason_zh` added, in the AI's chosen order. Empty in, empty out — no
    AI call is made if there's nothing to pick from."""
    if not candidates or limit <= 0:
        return []

    keyed = {_candidate_key(i): product for i, product in enumerate(candidates)}
    candidate_list = "\n".join(
        f'- {key}: "{product.get("name")}" — RM{product.get("price")}'
        for key, product in keyed.items()
    )

    prompt = f"""\
{narrative_prompt}

Here are the current colour-matched product candidates:
{candidate_list}

You MUST pick at least 1 and at most {limit} of these — never zero, there
is always at least one candidate above worth recommending. Choose
whichever genuinely fit this person's current state and recent pattern
best, in order of best fit first. Do not invent a candidate that isn't
listed above.

For each pick, write:
- `reason_en` / `reason_zh`: 2-3 sentences, as if lifted from the middle
  of a personal letter — sincere and tender, carrying real feeling rather
  than describing the product. Address the reader gently. Not marketing
  copy, not clinical, no bullet points. Ground it in the inner state and
  recent reflections above. Write genuinely in each language — not a
  literal translation of one into the other.
- `material_tag`: the stone/material name only, concise (1-4 words),
  cleanly cased (e.g. "Moss Agate", "Red Phantom Quartz") — drawn from the
  candidate's name above. English only, no bilingual pair needed.
"""

    schema = _build_schema(list(keyed.keys()))
    response = await _client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": _SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ],
        text_format=schema,
    )
    parsed = response.output_parsed

    picked: list[dict] = []
    seen_keys: set[str] = set()
    for pick in parsed.picks:
        key = pick.product_key.value
        if key in seen_keys:
            continue
        seen_keys.add(key)
        product = keyed[key]
        picked.append({**product, "reason_en": pick.reason_en, "reason_zh": pick.reason_zh, "material_tag": pick.material_tag})
        if len(picked) >= limit:
            break

    # The model is instructed to always pick at least one, but structured
    # output has no hard "non-empty list" guarantee — confirmed reproducible:
    # two back-to-back calls with the same input, one picked, one didn't.
    # Never let that show up to the user as "no products" when real,
    # colour-matched candidates genuinely exist — fall back to the first
    # `limit` candidates with a plain, honest reason instead of nothing.
    if not picked:
        for key in list(keyed.keys())[:limit]:
            product = keyed[key]
            picked.append({
                **product,
                "reason_en": f"A {product.get('name', 'piece')} matched to your current colour.",
                "reason_zh": f"根据你当前的颜色为你匹配的{product.get('name', '选品')}。",
                "material_tag": _guess_material(product.get("name")),
            })
    return picked
