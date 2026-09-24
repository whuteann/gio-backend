"""Deterministic scoring — a Python port of gio-member-app/lib/scoring.ts.

None of this is "AI" in the frontend either: it's rule-based math standing
in for an eventual AI step, and porting it faithfully is what makes the
gamification cascade (XP/streak/badges/recommendation) meaningful today
instead of every submission just being a no-op write.
"""

from app.services.content import (
    ARCHETYPE_KEYS,
    ARCHETYPES,
    BASELINE_ASSESSMENT,
    COLOUR_ORDER,
    DIMENSION_KEYS,
    FOCUS_COPY,
    READING_CATEGORY,
    truncate_words,
)


def seeded_hash(seed: str) -> int:
    h = 0
    for ch in seed:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def pick_phrasing(seed: str, options: list[str]) -> str:
    return options[seeded_hash(seed) % len(options)]


def colour_key_from_seed(seed: str) -> str:
    return COLOUR_ORDER[seeded_hash(seed) % len(COLOUR_ORDER)]


def normalize(raw_value: int) -> int:
    """1-5 raw answer -> 0-100 normalized value."""
    return round(((raw_value - 1) / 4) * 100)


def dimension_averages(answers: list[dict]) -> dict[str, int]:
    """answers: [{dimension, normalized_value}] -> {dimension: avg 0-100}."""
    result = {}
    for key in DIMENSION_KEYS:
        values = [a["normalized_value"] for a in answers if a["dimension"] == key]
        result[key] = round(sum(values) / len(values)) if values else 50
    return result


def resolve_focus_key(dims: dict[str, int]) -> str:
    needs = [
        ("emotional_energy", 100 - dims["emotional_energy"]),
        ("mental_clarity", 100 - dims["mental_clarity"]),
        ("inner_pressure", dims["inner_pressure"]),
        ("grounding", 100 - dims["grounding"]),
    ]
    needs.sort(key=lambda n: n[1], reverse=True)
    top_key, top_need = needs[0]
    return top_key if top_need >= 55 else "balanced"


def focus_label_for(focus_key: str) -> str:
    """The deterministic, English, human-readable focus label (e.g.
    "Rebuilding energy") for a resolve_focus_key() result — used to ground
    the AI outcome prompt (app/services/ai_outcome.py). Distinct from
    InnerStateSnapshot.current_focus, which holds the AI's own "ongoing
    journey" phrasing, not this label directly."""
    return FOCUS_COPY[focus_key]["focus"]


def reading_category_and_emoji(reading) -> dict:
    """Category chip + avatar emoji for an InnerReading listing card —
    deterministic from the reading's own stored pillar values via
    resolve_focus_key(), same principle as focus_label_for(). Missing
    pillars (an incomplete reading) fall back to the same default (50)
    dimension_averages() itself uses for a missing answer."""
    dims = {
        key: (getattr(reading, key) if getattr(reading, key) is not None else 50)
        for key in DIMENSION_KEYS
    }
    return READING_CATEGORY[resolve_focus_key(dims)]


def reading_content_for_plan(reading, premium: bool) -> dict:
    """Depth-gates an InnerReading's narrative content at read time (not at
    write time), so upgrading to Premium retroactively unlocks full depth on
    readings taken while on the free plan — same live-gating philosophy as
    the dashboard's trend chart. `reading.narrative`/`.life_area_insights`
    are AI-generated (docs/behaviour_log_0007.md Phase 4), not looked up
    from a static library keyed by focus — this function only gates what's
    already stored on the row. category/emoji are never gated — basic
    listing metadata, not depth content."""
    tag = reading_category_and_emoji(reading)
    if premium:
        return {
            "narrative": reading.narrative,
            "life_area_insights": reading.life_area_insights,
            "is_premium_content": True,
            "category": tag["category"],
            "emoji": tag["emoji"],
        }
    return {
        "narrative": truncate_words(reading.narrative, 100) if reading.narrative else reading.narrative,
        "life_area_insights": None,
        "is_premium_content": False,
        "category": tag["category"],
        "emoji": tag["emoji"],
    }


def score_from_birthdate(birthdate: str) -> dict:
    """Onboarding's Core Personality moment — deterministic from birthdate,
    framed in the product as an AI reading of it."""
    archetype = ARCHETYPE_KEYS[seeded_hash(birthdate) % len(ARCHETYPE_KEYS)]
    copy = ARCHETYPES[archetype]

    def pillar(name: str) -> int:
        return 42 + (seeded_hash(f"{birthdate}:{name}") % 49)

    return {
        "archetype": archetype,
        "icon": pick_phrasing(f"{birthdate}:icon", copy["icons"]),
        "thinking": pillar("thinking"),
        "emotional_sensitivity": pillar("emotionalSensitivity"),
        "adaptability": pillar("adaptability"),
        "willpower": pillar("willpower"),
        "overall_explanation": copy["overall"],
        "pillar_explanations": copy["pillars"],
    }


def score_baseline(answers: list[dict], seed_for_icon: str) -> dict:
    """Recalibration — the original A/B quiz. `answers`: [{index, choice}]."""
    tally = {key: 0 for key in ARCHETYPE_KEYS}
    pillar_values: dict[str, list[int]] = {"thinking": [], "emotionalSensitivity": [], "adaptability": [], "willpower": []}

    for a in answers:
        prompt = BASELINE_ASSESSMENT[a["index"]]
        option = prompt["option_a"] if a["choice"] == "A" else prompt["option_b"]
        tally[option["weight"]] += 1
        pillar_values[prompt["pillar"]].append(option["pillar_value"])

    archetype = max(ARCHETYPE_KEYS, key=lambda k: tally[k])
    copy = ARCHETYPES[archetype]

    def avg(values: list[int]) -> int:
        return round(sum(values) / len(values)) if values else 50

    return {
        "archetype": archetype,
        "icon": pick_phrasing(seed_for_icon, copy["icons"]),
        "thinking": avg(pillar_values["thinking"]),
        "emotional_sensitivity": avg(pillar_values["emotionalSensitivity"]),
        "adaptability": avg(pillar_values["adaptability"]),
        "willpower": avg(pillar_values["willpower"]),
        "overall_explanation": copy["overall"],
        "pillar_explanations": copy["pillars"],
    }
