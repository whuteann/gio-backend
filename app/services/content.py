"""Static content catalog — a Python port of gio-member-app/lib/blueprints.ts.

Deliberately kept as backend constants rather than DB tables: nothing here
is per-user data or ever queried/filtered in SQL, it's read wholesale and
either returned as-is (catalog endpoints) or hashed into (seeded variant
pools) — see the "Catalog / reference content" section of
docs/database-models-draft.md for the reasoning.
"""

from decimal import Decimal

DIMENSIONS = [
    {"key": "emotional_energy", "label": "Emotional Energy", "low_label": "Drained", "high_label": "Energised"},
    {"key": "mental_clarity", "label": "Mental Clarity", "low_label": "Foggy", "high_label": "Clear"},
    {"key": "inner_pressure", "label": "Inner Pressure", "low_label": "Light", "high_label": "Heavy"},
    {"key": "grounding", "label": "Grounding", "low_label": "Unsteady", "high_label": "Rooted"},
]
DIMENSION_KEYS = [d["key"] for d in DIMENSIONS]

FOCUS_COPY = {
    "emotional_energy": {"focus": "Rebuilding energy", "summary": "Your reserves are running low — small, gentle recharge matters most right now."},
    "mental_clarity": {"focus": "Finding clarity", "summary": "Things feel a little foggy. A slower pace could help the picture sharpen."},
    "inner_pressure": {"focus": "Releasing pressure", "summary": "You're carrying more than usual — this is a good moment to set something down."},
    "grounding": {"focus": "Regaining grounding", "summary": "You feel a little untethered. Reconnecting with routine could help you settle."},
    "balanced": {"focus": "Sustaining balance", "summary": "You're in a steady place across the board — a good moment to build on momentum."},
}

# Inner Reading listing metadata (category chip + avatar emoji), keyed by
# resolve_focus_key()'s output — deterministic, not AI, same principle as
# FOCUS_COPY above. Ports the values gio-member-app's old client-side
# FOCUS_TAG constant used to compute locally from a mock reading's
# dimensionScores; now served by the API instead (InnerReadingOut).
READING_CATEGORY = {
    "emotional_energy": {"category": "Personal", "emoji": "🌙"},
    "mental_clarity": {"category": "Decision Making", "emoji": "🌊"},
    "inner_pressure": {"category": "Work", "emoji": "🌿"},
    "grounding": {"category": "Recovery", "emoji": "🪨"},
    "balanced": {"category": "Reflection", "emoji": "✨"},
}

ARCHETYPES = {
    "steady_anchor": {
        "key": "steady_anchor", "name": "The Steady Anchor", "tagline": "Grounded, dependable, quietly unshakeable.",
        "traits": ["Grounded", "Dependable", "Composed"], "reminder": "Being capable doesn't mean you must manage everything alone.",
        "icons": ["🌳", "⚓️", "🪨"], "colour_reason": "You tend to carry more responsibility than you let on.",
        "overall": "You hold steady when things get loud around you. Others lean on your calm the way a ship leans on its anchor — you don't need the spotlight to be the reason a room feels safe.",
        "pillars": {
            "thinking": "You think in a measured, unhurried way, preferring solid ground over speed.",
            "emotionalSensitivity": "You feel things deeply but rarely let the surface show — steadiness is your love language.",
            "adaptability": "You adapt slowly and deliberately, re-anchoring before you move again.",
            "willpower": "Your willpower is quiet and relentless — you keep going long after the excitement fades.",
        },
    },
    "bright_spark": {
        "key": "bright_spark", "name": "The Bright Spark", "tagline": "Vivid, expressive, alive in the moment.",
        "traits": ["Expressive", "Vivid", "Spontaneous"], "reminder": "Your feelings are information, not something to manage away.",
        "icons": ["✨", "🔥", "🌟"], "colour_reason": "Your feelings move quickly, which can be tiring to sustain.",
        "overall": "You move through the world in colour. Your feelings arrive fast and full, and that same aliveness is what lets you connect, create and light up a room without even trying.",
        "pillars": {
            "thinking": "You think fast and intuitively, trusting the first flash of insight.",
            "emotionalSensitivity": "Your emotional range is wide and quick — you feel things vividly and in real time.",
            "adaptability": "You adapt on the fly, energised rather than unsettled by change.",
            "willpower": "Your willpower comes in bursts of inspiration rather than a steady grind.",
        },
    },
    "quiet_strategist": {
        "key": "quiet_strategist", "name": "The Quiet Strategist", "tagline": "Thoughtful, patient, always three steps ahead.",
        "traits": ["Observant", "Patient", "Analytical"], "reminder": "Not every plan needs to be perfect before you begin.",
        "icons": ["🦉", "♟️", "🧩"], "colour_reason": "You tend to think things through more than you rest.",
        "overall": "You see the shape of things before others do. You'd rather understand a system fully than rush an answer — patience is one of your quiet superpowers.",
        "pillars": {
            "thinking": "You think in structures and patterns, mapping things out before acting.",
            "emotionalSensitivity": "You process feelings internally and thoroughly, rarely reacting before reflecting.",
            "adaptability": "You prefer to study new ground before stepping onto it.",
            "willpower": "Your willpower is disciplined — you can sustain effort on things that don't feel exciting yet.",
        },
    },
    "open_horizon": {
        "key": "open_horizon", "name": "The Open Horizon", "tagline": "Curious, flexible, drawn to what's next.",
        "traits": ["Curious", "Flexible", "Open-Minded"], "reminder": "It's okay to finish what you started before chasing what's next.",
        "icons": ["🧭", "🌅", "🦋"], "colour_reason": "You're often moving toward what's next, rarely pausing fully.",
        "overall": "You're energised by possibility. New ground doesn't scare you — it invites you. Your flexibility is a genuine strength, letting you move where rigid people get stuck.",
        "pillars": {
            "thinking": "You think expansively, comfortable holding multiple possibilities at once.",
            "emotionalSensitivity": "You feel a wide emotional range and let it inform, rather than derail, your choices.",
            "adaptability": "You adapt easily and often seek change out rather than waiting for it.",
            "willpower": "Your willpower is fuelled by curiosity — momentum comes easiest when something feels new.",
        },
    },
}
ARCHETYPE_KEYS = list(ARCHETYPES.keys())

COLOURS = {
    "scarlet": {
        "key": "scarlet", "name": "Scarlet", "swatch": "#c0392b",
        "traits": ["Vitality", "Passion", "Courage"],
        "description": "A bold, energising red that awakens motivation and physical vitality.",
        "article": "Scarlet is the colour of movement — it's what the body reaches for when energy is running low and momentum needs a spark. It's associated with vitality, passion and courage: not recklessness, but the willingness to act on what matters.",
        "benefit": "You may benefit from more energy, motivation and a spark of courage.",
        "affirmations": ["I welcome energy and momentum back into my day.", "I act with courage, even in small steps."],
        "positive_traits": ["Energised", "Bold", "Passionate", "Decisive", "Alive"],
        "negative_traits": ["Impulsive", "Restless", "Impatient", "Quick-tempered", "Overextended"],
    },
    "russet": {
        "key": "russet", "name": "Russet", "swatch": "#8b4a2b",
        "traits": ["Stability", "Warmth", "Resilience"],
        "description": "A warm, earthy brown-red that steadies you and restores a sense of resilience.",
        "article": "Russet is the colour of solid ground — the warm brown-red of autumn leaves and turned soil. It carries stability rather than urgency, built slowly through repetition rather than a single grand gesture.",
        "benefit": "You may benefit from more stability, warmth and steady resilience.",
        "affirmations": ["I am steady, even when the ground feels uncertain.", "I build resilience one grounded step at a time."],
        "positive_traits": ["Steady", "Warm", "Resilient", "Reliable", "Patient"],
        "negative_traits": ["Stubborn", "Slow to change", "Guarded", "Overcautious", "Rigid"],
    },
    "gold": {
        "key": "gold", "name": "Gold", "swatch": "#b9902a",
        "traits": ["Confidence", "Abundance", "Radiance"],
        "description": "A warm, radiant gold that reflects confidence and sustained, balanced progress.",
        "article": "Gold is the colour of quiet achievement — not the loud win, but the steady accumulation of effort that's finally visible. It asks you to notice what's already working rather than chase more.",
        "benefit": "You may benefit from recognising your own progress and letting it build quiet confidence.",
        "affirmations": ["I trust the progress I've already made.", "I let my steady effort shine."],
        "positive_traits": ["Confident", "Radiant", "Generous", "Optimistic", "Accomplished"],
        "negative_traits": ["Complacent", "Overconfident", "Showy", "Entitled", "Coasting"],
    },
    "forest": {
        "key": "forest", "name": "Forest", "swatch": "#4a6b3d",
        "traits": ["Grounding", "Growth", "Renewal"],
        "description": "A deep, grounding green that supports steadiness, emotional recovery and sustainable growth.",
        "article": "Forest is the colour of steady, unhurried growth — the deep green of old trees rather than a new sprout. Especially supportive when pressure has been building: it asks you to root down, not push harder.",
        "benefit": "You may benefit from more grounding, balance and emotional recovery.",
        "affirmations": ["I choose steady progress over unnecessary rush.", "I create space to grow with clarity and calm."],
        "positive_traits": ["Grounded", "Balanced", "Nurturing", "Renewing", "Patient"],
        "negative_traits": ["Withdrawn", "Overcommitted", "Depleted", "Avoidant", "Slow to ask for help"],
    },
    "ocean": {
        "key": "ocean", "name": "Ocean", "swatch": "#3f8f8a",
        "traits": ["Calm", "Clarity", "Communication"],
        "description": "A cool, clear blue-teal that supports calm thinking and honest communication.",
        "article": "Ocean is the colour of a clear mind — cool, spacious and unclouded. When thoughts feel tangled, ocean points toward stillness rather than more input: fewer tabs open, one conversation instead of many.",
        "benefit": "You may benefit from a calmer mind and clearer, more honest communication.",
        "affirmations": ["I think clearly and speak with calm honesty.", "I create quiet space for my mind to settle."],
        "positive_traits": ["Calm", "Clear-headed", "Honest", "Reflective", "Composed"],
        "negative_traits": ["Detached", "Overanalytical", "Indecisive", "Distant", "Emotionally guarded"],
    },
}
COLOUR_ORDER = ["scarlet", "russet", "gold", "forest", "ocean"]

FOCUS_TO_COLOUR = {
    "Rebuilding energy": {"colour_key": "scarlet", "tags": ["energy", "lift"], "routine": "A 10-minute walk before noon, away from screens."},
    "Finding clarity": {"colour_key": "ocean", "tags": ["clarity", "focus"], "routine": "Write down the one thing that matters most today, before anything else."},
    "Releasing pressure": {"colour_key": "forest", "tags": ["release", "calm"], "routine": "Set a 15-minute timer to do nothing but breathe and let your shoulders drop."},
    "Regaining grounding": {"colour_key": "russet", "tags": ["grounding", "steadiness"], "routine": "Stand barefoot for two minutes and name five things you can feel."},
    "Sustaining balance": {"colour_key": "gold", "tags": ["calm", "reflection"], "routine": "Keep doing what's working — a short reflection tonight will reinforce it."},
}

BADGE_DEFINITIONS = [
    {"key": "three_day_streak", "group": "consistency", "title": "Three Days Steady", "description": "Reflected three days in a row.", "icon": "🌤️"},
    {"key": "two_week_rhythm", "group": "consistency", "title": "Two-Week Rhythm", "description": "Kept a 14-day reflection streak.", "icon": "🕰️"},
    {"key": "first_insight", "group": "depth", "title": "First Insight", "description": "Completed your first Inner Reading.", "icon": "🔍"},
    {"key": "deep_diver", "group": "depth", "title": "Deep Diver", "description": "Completed five Inner Readings.", "icon": "🌊"},
    {"key": "first_bloom", "group": "growth", "title": "First Bloom", "description": "Grew your Garden to full bloom in a week.", "icon": "🌸"},
    {"key": "momentum", "group": "growth", "title": "Momentum", "description": "Earned 300 total XP.", "icon": "⚡"},
]
BADGE_DEFINITIONS_BY_KEY = {b["key"]: b for b in BADGE_DEFINITIONS}


def _reward_golden_hour(ctx: dict) -> bool:
    return ctx["xp"] >= 50


def _reward_grounding_ritual(ctx: dict) -> bool:
    return ctx["xp"] >= 150


def _reward_founding_candle(ctx: dict) -> bool:
    return ctx["streak_best"] >= 7


def _reward_archetype_deep_dive(ctx: dict) -> bool:
    return len(ctx["badges"]) >= 3


REWARD_DEFINITIONS = [
    {"key": "golden_hour_playlist", "title": "Golden Hour Playlist", "description": "A wind-down playlist curated for grounding evenings.", "icon": "🎧", "requirement": "Reach 50 XP", "is_eligible": _reward_golden_hour},
    {"key": "grounding_ritual_guide", "title": "Grounding Ritual Guide", "description": "A short guide to a 5-minute grounding ritual.", "icon": "📖", "requirement": "Reach 150 XP", "is_eligible": _reward_grounding_ritual},
    {"key": "founding_streak_candle", "title": "Founding Streak Candle Discount", "description": "15% toward any candle in the Gio store.", "icon": "🕯️", "requirement": "Reach a 7-day streak", "is_eligible": _reward_founding_candle},
    {"key": "archetype_deep_dive", "title": "Archetype Deep-Dive Report", "description": "An extended written breakdown of your archetype.", "icon": "📜", "requirement": "Earn 3 badges", "is_eligible": _reward_archetype_deep_dive},
]
REWARD_DEFINITIONS_BY_KEY = {r["key"]: r for r in REWARD_DEFINITIONS}

# Premium pricing — deterministic, confirmed pricing (docs/behaviour_log_0009.md),
# not something an AI call or a database row should own. Yearly is 12
# months at the monthly rate, discounted 20%: 19.90 * 12 * 0.80 = 191.04.
# Displayed and charged as this flat amount — no "effective RM/mo" framing.
PREMIUM_PRICING = {
    "MONTHLY": {"amount": Decimal("19.90"), "currency": "MYR"},
    "YEARLY": {"amount": Decimal("191.04"), "currency": "MYR"},
}

# (pillar, prompt, optionA{label,weight,pillarValue}, optionB{...})
BASELINE_ASSESSMENT = [
    {"pillar": "thinking", "prompt": "When a hard decision shows up, you tend to...",
     "option_a": {"label": "Map it out carefully before acting", "weight": "quiet_strategist", "pillar_value": 85},
     "option_b": {"label": "Go with your first instinct", "weight": "bright_spark", "pillar_value": 40}},
    {"pillar": "thinking", "prompt": "In a new situation, you usually...",
     "option_a": {"label": "Look for the underlying pattern", "weight": "quiet_strategist", "pillar_value": 80},
     "option_b": {"label": "Explore and see what happens", "weight": "open_horizon", "pillar_value": 45}},
    {"pillar": "emotionalSensitivity", "prompt": "When someone close to you is upset, you...",
     "option_a": {"label": "Feel it almost as strongly as they do", "weight": "bright_spark", "pillar_value": 85},
     "option_b": {"label": "Stay calm so you can help steadily", "weight": "steady_anchor", "pillar_value": 40}},
    {"pillar": "emotionalSensitivity", "prompt": "Your emotions during the day are usually...",
     "option_a": {"label": "Vivid and quick to shift", "weight": "bright_spark", "pillar_value": 80},
     "option_b": {"label": "Steady and slow to move", "weight": "steady_anchor", "pillar_value": 35}},
    {"pillar": "adaptability", "prompt": "When plans suddenly change, you...",
     "option_a": {"label": "Adjust quickly and keep moving", "weight": "open_horizon", "pillar_value": 85},
     "option_b": {"label": "Prefer to re-anchor before continuing", "weight": "steady_anchor", "pillar_value": 40}},
    {"pillar": "adaptability", "prompt": "A new environment feels...",
     "option_a": {"label": "Exciting — new ground to explore", "weight": "open_horizon", "pillar_value": 80},
     "option_b": {"label": "Something to study before diving in", "weight": "quiet_strategist", "pillar_value": 45}},
    {"pillar": "willpower", "prompt": "When something gets hard, you...",
     "option_a": {"label": "Keep going, one steady step at a time", "weight": "steady_anchor", "pillar_value": 85},
     "option_b": {"label": "Find a spark to push through", "weight": "bright_spark", "pillar_value": 55}},
    {"pillar": "willpower", "prompt": "You keep long-term commitments by...",
     "option_a": {"label": "Sticking to a plan even when it's dull", "weight": "quiet_strategist", "pillar_value": 80},
     "option_b": {"label": "Staying open to whatever keeps you moving", "weight": "open_horizon", "pillar_value": 50}},
]

JOURNAL_MOODS = ["Calm", "Hopeful", "Tired", "Anxious", "Grateful", "Content", "Overwhelmed", "Energised"]
JOURNAL_THEMES = ["Growth", "Responsibility", "Relationships", "Self-Care", "Work", "Clarity", "Rest", "Gratitude"]


def truncate_words(text: str, limit: int = 100) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]) + "…"
