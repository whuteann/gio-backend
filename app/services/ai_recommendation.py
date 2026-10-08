"""AI recommendation generation — produces one unifying "letter" plus a
fixed-shape product/phone-case set, all in a single structured-output
call:
  - feature product, from the focus-matched material-affinity type
    (mandatory whenever that type has any stock for today's colour)
  - one secondary product per *other* stone type (best-effort per type,
    blank for a type with no stock — never substituted from a different
    type, so the set stays one-of-each-type rather than "3 from whichever
    pool had stock")
  - primary phone case (mandatory whenever any case candidate exists)
  - up to 1 secondary phone case (best-effort, blank is fine)
No premium/free gating here — every user gets the same best-effort
target. See docs/recommendation_engine.md for the full pipeline this
sits in, and docs/behaviour_log_0012.md for the original per-product
version this replaced.

Same "constrained selection" mechanism as AffirmationId/InsightId/
ReflectionQuestionId (app/schemas/ai_outcome.py): candidates are keyed
positionally and wrapped in dynamically-built Enums, so the model is
structurally incapable of returning a candidate that wasn't actually in
this call's list. Each stone type gets its own isolated pool/Enum/field,
so a Jade pick can never leak into the Nephrite slot or vice versa.

Mandatory picks (`feature_pick`, `primary_case_pick`) are required
*single* fields rather than lists — unlike a required `list[...]` field,
which structured output can legally return empty (confirmed reproducible
for the old all-list phone case design), a required single field cannot
be empty by construction. The best-effort picks (`secondary_pick_<type>`,
`secondary_case_pick`) are required-but-*nullable* single fields, so a
genuine "nothing else fits" is representable without risking the model
silently omitting the field.

The `stone_type`/`category` tag on every stone item is set in code from
which pool it was drawn from, never left to the AI to name — it's a
structural fact (which list this is), not a judgment call.
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


def _keyed(candidates: list[dict], prefix: str) -> dict[str, dict]:
    return {f"{prefix}{i + 1:02d}": c for i, c in enumerate(candidates)}


def _stone_pick_model(name: str, key_enum: type[Enum]) -> type[BaseModel]:
    return create_model(
        name,
        product_key=(key_enum, ...),
        material_tag=(str, ...),
        reason_en=(str, ...),
        reason_zh=(str, ...),
    )


def _build_schema(
    feature_keyed: dict[str, dict], secondary_keyed_by_type: dict[str, dict[str, dict]], case_keyed: dict[str, dict]
) -> tuple[type[BaseModel], dict[str, str]]:
    """Returns (schema, secondary_field_by_type) — the latter maps each
    secondary stone type to the schema field name carrying its pick, so
    the caller can tag results with the right `stone_type` afterwards."""
    FeatureKey = Enum("FeatureKey", {k: k for k in feature_keyed})
    fields: dict[str, tuple] = {
        "letter_en": (str, ...),
        "letter_zh": (str, ...),
        "feature_pick": (_stone_pick_model("FeaturePick", FeatureKey), ...),
    }

    secondary_field_by_type: dict[str, str] = {}
    for stone_type, keyed in secondary_keyed_by_type.items():
        if not keyed:
            # Nothing to build an Enum from, and nothing to pick — this
            # type simply has no stock for today's colour, stays blank.
            continue
        TypeKey = Enum(f"{stone_type}Key", {k: k for k in keyed})
        field_name = f"secondary_pick_{stone_type.lower()}"
        fields[field_name] = (_stone_pick_model(f"{stone_type}Pick", TypeKey) | None, ...)
        secondary_field_by_type[stone_type] = field_name

    # Only ask for phone case picks when there's actually something to pick
    # from — building an Enum from an empty mapping raises, and there's
    # nothing meaningful to constrain-select from zero candidates anyway
    # (see app/services/lumenart.py — empty only if the cache has never
    # successfully populated, e.g. a brand-new deploy before the first
    # lazy refresh succeeds).
    if case_keyed:
        CaseKey = Enum("CaseKey", {k: k for k in case_keyed})
        CasePick = create_model(
            "PhoneCasePick",
            case_key=(CaseKey, ...),
            reason_en=(str, ...),
            reason_zh=(str, ...),
        )
        fields["primary_case_pick"] = (CasePick, ...)
        # A second pick only makes sense with a second distinct candidate.
        if len(case_keyed) >= 2:
            fields["secondary_case_pick"] = (CasePick | None, ...)

    return create_model("RecommendationGeneration", **fields), secondary_field_by_type


async def generate_recommendation(
    *,
    narrative_prompt: str,
    focus_label: str,
    material_affinity: str,
    stone_candidates_by_type: dict[str, list[dict]],
    phone_case_candidates: list[dict],
) -> dict:
    """Returns {"letter_en", "letter_zh", "feature": dict|None, "others":
    [dict] (one per non-feature type, each tagged `stone_type`),
    "phone_case": [dict] (up to 2, primary first)}. If the feature type
    (the focus-matched material affinity) has zero stock for today's
    colour, the whole stones half returns empty — same conservative
    empty-in-empty-out contract as before this type-coverage change
    (confirmed-acceptable behaviour: a genuinely out-of-stock match
    degrading to "no product recommendation today" rather than
    substituting a different type as a fake feature). Phone case
    candidates are independent: if there are none, `phone_case` is just
    `[]`, it never blocks the stone half."""
    feature_candidates = stone_candidates_by_type.get(material_affinity) or []
    if not feature_candidates:
        return _EMPTY_RESULT

    feature_keyed = _keyed(feature_candidates, "F")
    secondary_keyed_by_type = {
        stone_type: _keyed(candidates, stone_type[0].upper())
        for stone_type, candidates in stone_candidates_by_type.items()
        if stone_type != material_affinity
    }
    case_keyed = _keyed(phone_case_candidates, "C")

    feature_list = "\n".join(f'- {k}: "{c.get("name")}" — RM{c.get("price")}' for k, c in feature_keyed.items())

    secondary_blocks = []
    for stone_type, keyed in secondary_keyed_by_type.items():
        if not keyed:
            continue
        candidate_list = "\n".join(f'- {k}: "{c.get("name")}" — RM{c.get("price")}' for k, c in keyed.items())
        field_name = f"secondary_pick_{stone_type.lower()}"
        secondary_blocks.append(f"""
{stone_type} candidates (a different stone type from the feature pick above — \
pick from this list only, never mix it with another type's list):
{candidate_list}

Default to picking one of these for `{field_name}` — only set it to \
`null` if none of these {stone_type} candidates are a genuinely good fit, \
not as your default.""")
    secondary_block = "\n".join(secondary_blocks)

    case_block = ""
    if case_keyed:
        case_list = "\n".join(f'- {k}: "{c.get("name")}" — RM{c.get("price")}' for k, c in case_keyed.items())
        secondary_line = (
            "\n\nDefault to also picking a `secondary_case_pick` — there are "
            f"{len(case_keyed)} candidates here, so there is almost always a second "
            "reasonable option. Only leave it `null` if the remaining candidates are "
            "genuinely not worth suggesting, not as your default."
            if len(case_keyed) >= 2
            else ""
        )
        case_block = f"""

Here are the current phone case candidates (a separate, unrelated product \
line — not stones, don't connect them to the material affinity above):
{case_list}

Pick exactly 1 of these as `primary_case_pick` — never skip this, there \
is always at least one worth recommending.{secondary_line} \
`reason_en`/`reason_zh`: 1-2 sentences, same letter voice as above, brief \
— this is its own small gift, not a stone, so don't force a tie to the \
material affinity above."""

    prompt = f"""\
{narrative_prompt}

This person's focus right now is "{focus_label}", and their matched \
material affinity is {material_affinity} — the feature candidates below \
are already filtered to that material, so every one of them already fits \
on that count; pick between them based on the rest of their state instead.

Here are the current colour- and material-matched FEATURE candidates \
({material_affinity}):
{feature_list}

Pick exactly one FEATURE pick (`feature_pick`) from the list above — the \
single best fit, the one the letter is really about. Do not invent a \
candidate that isn't listed.

The product set also includes one pick from each of the other stone \
types below, each independent of the feature pick and of each other:
{secondary_block}

For `feature_pick` and every secondary pick:
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

    schema, secondary_field_by_type = _build_schema(feature_keyed, secondary_keyed_by_type, case_keyed)
    response = await _client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": _SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ],
        text_format=schema,
    )
    parsed = response.output_parsed

    def _to_item(pick, keyed: dict, stone_type: str) -> dict:
        product = keyed[pick.product_key.value]
        return {
            **product, "reason_en": pick.reason_en, "reason_zh": pick.reason_zh,
            "material_tag": pick.material_tag, "stone_type": stone_type,
        }

    feature = _to_item(parsed.feature_pick, feature_keyed, material_affinity)

    others: list[dict] = []
    for stone_type, field_name in secondary_field_by_type.items():
        pick = getattr(parsed, field_name, None)
        if pick is not None:
            others.append(_to_item(pick, secondary_keyed_by_type[stone_type], stone_type))

    phone_case: list[dict] = []
    primary_case_pick = getattr(parsed, "primary_case_pick", None)
    if case_keyed and primary_case_pick:
        # Mandatory — guaranteed non-null by the schema (required single
        # field) whenever case_keyed is non-empty, see _build_schema.
        primary_product = case_keyed[primary_case_pick.case_key.value]
        phone_case.append({**primary_product, "reason_en": primary_case_pick.reason_en, "reason_zh": primary_case_pick.reason_zh})

        secondary_case_pick = getattr(parsed, "secondary_case_pick", None)
        if secondary_case_pick and secondary_case_pick.case_key.value != primary_case_pick.case_key.value:
            secondary_product = case_keyed[secondary_case_pick.case_key.value]
            phone_case.append({
                **secondary_product, "reason_en": secondary_case_pick.reason_en, "reason_zh": secondary_case_pick.reason_zh,
            })

    return {
        "letter_en": parsed.letter_en,
        "letter_zh": parsed.letter_zh,
        "feature": feature,
        "others": others,
        "phone_case": phone_case,
    }
