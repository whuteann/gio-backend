"""AI recommendation generation — produces one unifying "letter" plus a
feature product, a short product list, and (when any phone case candidate
exists) at least one phone case pick, all in a single structured-output
call. See docs/recommendation_engine.md for the full pipeline this sits
in, and docs/behaviour_log_0012.md for the original per-product version
this replaced.

Same "constrained selection" mechanism as AffirmationId/InsightId/
ReflectionQuestionId (app/schemas/ai_outcome.py): candidates are keyed
positionally ("S01", "S02", ... / "C01", "C02", ...) and wrapped in
dynamically-built Enums, so the model is structurally incapable of
returning a candidate that wasn't actually in this call's list.
`feature_pick` is a required single field (not a list), so — unlike the
old version's `picks: list[...]`, which structured output could legally
return empty (confirmed reproducible) — there's no "zero picks" case to
defend against for the feature pick by construction.
"""

from enum import Enum

from openai import AsyncOpenAI
from pydantic import BaseModel, create_model

from app.config import settings

_client = AsyncOpenAI(api_key=settings.openai_api_key)

# A devoted-letter-writer persona — someone who puts another person's
# feelings into words the way a trusted scribe writes on their behalf, so
# `reason`/`letter` reads as lines from a real letter rather than product
# copy. Described directly here rather than naming its inspiration, so the
# voice stays controllable instead of imitating a specific character.
_SYSTEM_MESSAGE = (
    "You are a devoted letter-writer for a wellness app called Auren — someone who "
    "writes short, sincere letters carrying another person's feelings into words. "
    "You must strictly follow the required JSON structure."
)

_EMPTY_RESULT = {"letter_en": "", "letter_zh": "", "feature": None, "others": [], "phone_case": []}


def _stone_key(index: int) -> str:
    return f"S{index + 1:02d}"


def _case_key(index: int) -> str:
    return f"C{index + 1:02d}"


def _build_schema(stone_keys: list[str], case_keys: list[str]) -> type[BaseModel]:
    StoneKey = Enum("StoneKey", {k: k for k in stone_keys})
    StonePick = create_model(
        "StonePick",
        product_key=(StoneKey, ...),
        material_tag=(str, ...),
        reason_en=(str, ...),
        reason_zh=(str, ...),
    )
    fields = {
        "letter_en": (str, ...),
        "letter_zh": (str, ...),
        "feature_pick": (StonePick, ...),
        "other_picks": (list[StonePick], ...),
    }
    # Only ask for phone case picks when there's actually something to pick
    # from — building an Enum from an empty mapping raises, and there's
    # nothing meaningful to constrain-select from zero candidates anyway
    # (see app/services/lumenart.py — empty only if the cache has never
    # successfully populated, e.g. a brand-new deploy before the first
    # lazy refresh succeeds).
    if case_keys:
        CaseKey = Enum("CaseKey", {k: k for k in case_keys})
        CasePick = create_model(
            "PhoneCasePick",
            case_key=(CaseKey, ...),
            reason_en=(str, ...),
            reason_zh=(str, ...),
        )
        fields["phone_case_picks"] = (list[CasePick], ...)
    return create_model("RecommendationGeneration", **fields)


async def generate_recommendation(
    *,
    narrative_prompt: str,
    focus_label: str,
    material_affinity: str,
    stone_candidates: list[dict],
    phone_case_candidates: list[dict],
    limit: int,
) -> dict:
    """Returns {"letter_en", "letter_zh", "feature": dict|None, "others":
    [dict], "phone_case": [dict]}. Empty stone_candidates (vendor down, or
    genuinely nothing matched) returns everything empty — same
    empty-in-empty-out contract app/services/recommendation.py already
    expects from the product half. Phone case candidates are independent:
    if there are none, `phone_case` is just `[]`, it never blocks the
    stone half."""
    if not stone_candidates or limit <= 0:
        return _EMPTY_RESULT

    stone_keyed = {_stone_key(i): c for i, c in enumerate(stone_candidates)}
    case_keyed = {_case_key(i): c for i, c in enumerate(phone_case_candidates)}

    stone_list = "\n".join(f'- {k}: "{c.get("name")}" — RM{c.get("price")}' for k, c in stone_keyed.items())

    case_block = ""
    if case_keyed:
        case_list = "\n".join(f'- {k}: "{c.get("name")}" — RM{c.get("price")}' for k, c in case_keyed.items())
        case_block = f"""

Here are the current phone case candidates (a separate, unrelated product \
line — not stones, don't connect them to the material affinity above):
{case_list}

Pick exactly 1 of these in `phone_case_picks` — never zero, there is \
always at least one worth recommending, and never more than one. \
`reason_en`/`reason_zh`: 1-2 sentences, same letter voice as above, brief \
— this is its own small gift, not a stone, so don't force a tie to the \
material affinity above."""

    prompt = f"""\
{narrative_prompt}

This person's focus right now is "{focus_label}", and their matched \
material affinity is {material_affinity} — the stone candidates below are \
already filtered to that material, so every one of them already fits on \
that count; pick between them based on the rest of their state instead.

Here are the current colour- and material-matched stone candidates:
{stone_list}

Pick exactly one FEATURE pick (`feature_pick`) — the single best fit, the \
one the letter is really about — and up to {max(limit - 1, 0)} further \
picks in `other_picks` (an empty list is fine if nothing else genuinely \
fits as well). Do not invent a candidate that isn't listed above.

For `feature_pick` and every item in `other_picks`:
- `reason_en` / `reason_zh`: 2-3 sentences, as if lifted from the middle \
of a personal letter — sincere and tender, carrying real feeling rather \
than describing the product. Not marketing copy, not clinical, no bullet \
points. Ground it in the inner state and recent reflections above. Write \
genuinely in each language — not a literal translation of one into the \
other.
- `material_tag`: the stone/material name only, concise (1-4 words), \
cleanly cased (e.g. "Moss Agate", "Red Phantom Quartz") — drawn from the \
candidate's name above. English only, no bilingual pair needed.

`letter_en` / `letter_zh`: write ONE unifying letter, 3-5 sentences, \
tying together this person's current focus ("{focus_label}"), their \
state, and why the feature pick in particular fits this moment — the \
single piece of writing this whole recommendation is built around, not a \
fragment or a summary of the picks above.
{case_block}
"""

    schema = _build_schema(list(stone_keyed.keys()), list(case_keyed.keys()))
    response = await _client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": _SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ],
        text_format=schema,
    )
    parsed = response.output_parsed

    def _to_item(pick, keyed: dict) -> dict:
        product = keyed[pick.product_key.value]
        return {**product, "reason_en": pick.reason_en, "reason_zh": pick.reason_zh, "material_tag": pick.material_tag}

    feature = _to_item(parsed.feature_pick, stone_keyed)
    seen = {parsed.feature_pick.product_key.value}
    others: list[dict] = []
    for pick in parsed.other_picks:
        key = pick.product_key.value
        if key in seen:
            continue
        seen.add(key)
        others.append(_to_item(pick, stone_keyed))
        if len(others) >= max(limit - 1, 0):
            break

    phone_case: list[dict] = []
    picks_attr = getattr(parsed, "phone_case_picks", None)
    if case_keyed and picks_attr:
        # Capped at exactly 1 regardless of what the model actually
        # returns — the prompt says "exactly 1" but structured output
        # gives no hard guarantee of that count either way.
        pick = picks_attr[0]
        product = case_keyed[pick.case_key.value]
        phone_case.append({**product, "reason_en": pick.reason_en, "reason_zh": pick.reason_zh})

    return {
        "letter_en": parsed.letter_en,
        "letter_zh": parsed.letter_zh,
        "feature": feature,
        "others": others,
        "phone_case": phone_case,
    }
