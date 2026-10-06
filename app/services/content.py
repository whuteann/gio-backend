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

# focus_zh/summary_zh: deterministic translations, not AI-written — same
# principle as AFFIRMATIONS/INSIGHTS below. Feeds RecommendationProfile's
# current_focus_zh/summary_zh (docs/behaviour_log_0012.md).
FOCUS_COPY = {
    "emotional_energy": {
        "focus": "Rebuilding energy", "focus_zh": "重建能量",
        "summary": "Your reserves are running low — small, gentle recharge matters most right now.",
        "summary_zh": "你的储备正在减少——此刻最重要的是温和地小小充电。",
    },
    "mental_clarity": {
        "focus": "Finding clarity", "focus_zh": "寻找清晰",
        "summary": "Things feel a little foggy. A slower pace could help the picture sharpen.",
        "summary_zh": "一切感觉有些模糊。放慢脚步，画面会渐渐清晰。",
    },
    "inner_pressure": {
        "focus": "Releasing pressure", "focus_zh": "释放压力",
        "summary": "You're carrying more than usual — this is a good moment to set something down.",
        "summary_zh": "你此刻承担得比平常更多——是时候放下一些东西了。",
    },
    "grounding": {
        "focus": "Regaining grounding", "focus_zh": "重新扎根",
        "summary": "You feel a little untethered. Reconnecting with routine could help you settle.",
        "summary_zh": "你感觉有些漂浮不定。回归日常习惯能帮你安定下来。",
    },
    "balanced": {
        "focus": "Sustaining balance", "focus_zh": "维持平衡",
        "summary": "You're in a steady place across the board — a good moment to build on momentum.",
        "summary_zh": "你目前整体处于稳定状态——正是乘势而上的好时机。",
    },
}

# Inner Reading listing metadata (category chip + avatar emoji), keyed by
# resolve_focus_key()'s output — deterministic, not AI, same principle as
# FOCUS_COPY above. Ports the values gio-member-app's old client-side
# FOCUS_TAG constant used to compute locally from a mock reading's
# dimensionScores; now served by the API instead (InnerReadingOut).
FOCUS_CATEGORY = {
    "emotional_energy": {"category": "Personal", "emoji": "🌙"},
    "mental_clarity": {"category": "Decision Making", "emoji": "🌊"},
    "inner_pressure": {"category": "Work", "emoji": "🌿"},
    "grounding": {"category": "Recovery", "emoji": "🪨"},
    "balanced": {"category": "Reflection", "emoji": "✨"},
}

# Curated affirmation/insight/reflection-question library —
# docs/behaviour_log_0011.md. The AI's job for these three fields moved
# from free generation to *selecting* the best-fitting id from here
# (grounded on dims/focus/memory, same inputs as before); the resolved
# bilingual text below is what actually gets stored/shown. Deterministic
# content, not AI-written — same principle as FOCUS_COPY/FOCUS_CATEGORY.
# Every id here also doubles as a gamification "unlock" key
# (UserUnlockedContent) — the first time an id is selected for a user,
# it's added to their permanent collection.
AFFIRMATIONS = {
    "AFF01": {"en": "I am steady, even when things around me are not.", "zh": "即使身边风雨不定，我依然稳如磐石。"},
    "AFF02": {"en": "I can move forward without forcing everything into place.", "zh": "我可以向前迈进，无需强求一切就位。"},
    "AFF03": {"en": "My energy will return; I don't have to force it today.", "zh": "我的能量终会回来，今天无需勉强。"},
    "AFF04": {"en": "I am allowed to rest without earning it first.", "zh": "我值得休息，不必先证明自己配得上。"},
    "AFF05": {"en": "Clarity comes when I stop demanding it.", "zh": "当我不再强求时，清晰自会浮现。"},
    "AFF06": {"en": "I trust myself to figure this out, one step at a time.", "zh": "我相信自己能一步一步理清一切。"},
    "AFF07": {"en": "I don't have to carry everything at full intensity.", "zh": "我不必用尽全力扛起一切。"},
    "AFF08": {"en": "I am capable of holding both effort and ease.", "zh": "我既能努力，也能从容。"},
    "AFF09": {"en": "Small steps still count as moving forward.", "zh": "小小的步伐，依然是前进。"},
    "AFF10": {"en": "I release what isn't mine to carry.", "zh": "我放下那些本不属于我的重担。"},
    "AFF11": {"en": "I am grounded in who I am, not what I do.", "zh": "我的根基是我是谁，而非我做了什么。"},
    "AFF12": {"en": "My feelings are information, not instructions.", "zh": "我的情绪是讯息，而非命令。"},
    "AFF13": {"en": "I can be gentle with myself and still grow.", "zh": "我可以温柔待己，同时依然成长。"},
    "AFF14": {"en": "Today's pace is enough.", "zh": "今天的步调，已经足够。"},
    "AFF15": {"en": "I am building something steady, one day at a time.", "zh": "我正一天天地，建立稳固的自己。"},
    "AFF16": {"en": "I don't need to have it all figured out yet.", "zh": "我不必现在就把一切想清楚。"},
    "AFF17": {"en": "I choose calm over urgency where I can.", "zh": "能选择时，我选择平静而非匆忙。"},
    "AFF18": {"en": "I am exactly where I need to be right now.", "zh": "此刻，我正处在该在的地方。"},
    "AFF19": {"en": "My worth isn't measured by how much I get done.", "zh": "我的价值，不由完成多少事来衡量。"},
    "AFF20": {"en": "I trust the process, even when I can't see the outcome.", "zh": "即使看不见结果，我依然相信过程。"},
}

REFLECTION_QUESTIONS = {
    "REF01": {"en": "What would it feel like to do less today, on purpose?", "zh": "如果今天刻意少做一些，会是什么感觉？"},
    "REF02": {"en": "What's one thing you're carrying that isn't actually yours?", "zh": "有哪一件事，其实并不是你该扛的？"},
    "REF03": {"en": "Where could you build in five quiet minutes today?", "zh": "今天你能在哪里挤出五分钟的安静？"},
    "REF04": {"en": "What's the smallest version of progress you'd accept today?", "zh": "今天你能接受的、最小的进步是什么？"},
    "REF05": {"en": "What are you afraid will happen if you slow down?", "zh": "如果放慢脚步，你担心会发生什么？"},
    "REF06": {"en": "Who or what recharges you, and when did you last make time for it?", "zh": "什么人或事能让你充电？你上次留时间给它是什么时候？"},
    "REF07": {"en": "What's one expectation you could quietly let go of this week?", "zh": "这周你能悄悄放下哪一项期待？"},
    "REF08": {"en": "What does \"enough\" look like for you today?", "zh": "对你来说，今天的\"足够\"是什么样子？"},
    "REF09": {"en": "What pattern do you notice repeating in how you feel lately?", "zh": "最近你的情绪中，反复出现了什么模式？"},
    "REF10": {"en": "What would you tell a friend feeling exactly this way?", "zh": "如果朋友有同样的感受，你会对他说什么？"},
    "REF11": {"en": "What's one small thing that's actually going well right now?", "zh": "此刻，有哪件小事其实进展得不错？"},
    "REF12": {"en": "Where are you being harder on yourself than the situation calls for?", "zh": "在哪件事上，你对自己比情况所需更苛刻？"},
    "REF13": {"en": "What's underneath the tiredness — is it physical, or something else?", "zh": "疲惫底下是什么？是身体，还是别的原因？"},
    "REF14": {"en": "What would it look like to trust yourself a little more today?", "zh": "今天多信任自己一点，会是什么样子？"},
    "REF15": {"en": "What's one boundary that would make today feel lighter?", "zh": "设下哪一条界限，会让今天轻松一些？"},
    "REF16": {"en": "What are you making more complicated than it needs to be?", "zh": "有什么事，被你想得比实际更复杂？"},
    "REF17": {"en": "What's one thing you can control today, when so much feels uncertain?", "zh": "在诸多不确定中，今天你能掌控的是什么？"},
    "REF18": {"en": "How would you know if you were actually taking care of yourself?", "zh": "你怎么知道自己是否真正在照顾自己？"},
    "REF19": {"en": "What's the story you're telling yourself about today, and is it true?", "zh": "你在对自己讲一个怎样的\"今天\"的故事？它真实吗？"},
    "REF20": {"en": "What would \"good enough\" look like, instead of perfect?", "zh": "如果不追求完美，\"足够好\"会是什么样子？"},
}

INSIGHTS = {
    "INS01": {"en": "Your reserves are running low — today's task is recovery, not achievement.", "zh": "你的能量储备正在减少——今天的任务是恢复，而非成就。"},
    "INS02": {"en": "There's a quiet tiredness beneath the surface that's worth naming.", "zh": "表面之下有一种安静的疲惫，值得被看见。"},
    "INS03": {"en": "Your energy dips are a reminder that rest is productive too.", "zh": "能量的起伏提醒着你，休息也是一种成效。"},
    "INS04": {"en": "Low energy isn't failure — it's a signal to slow down.", "zh": "低能量不是失败，而是放慢脚步的信号。"},
    "INS05": {"en": "Your thoughts are carrying more static than usual right now.", "zh": "此刻你的思绪比平时更多了些杂音。"},
    "INS06": {"en": "Fog usually means bandwidth, not ability — it will lift.", "zh": "迷雾通常关乎精力，而非能力——它终会散去。"},
    "INS07": {"en": "Clarity returns with less input, not more effort.", "zh": "清晰往往在减少输入、而非加倍努力时回归。"},
    "INS08": {"en": "Today's uncertainty is temporary, even if it doesn't feel that way.", "zh": "今天的不确定只是暂时的，即使感觉并非如此。"},
    "INS09": {"en": "You're holding more than usual — some of it isn't yours to carry.", "zh": "你此刻承担得比平常更多——其中有些并不属于你。"},
    "INS10": {"en": "Pressure builds when expectations outpace capacity — yours have lately.", "zh": "当期待超出承受力时，压力便会累积——你最近正是如此。"},
    "INS11": {"en": "What feels urgent right now may not be as urgent as it seems.", "zh": "此刻感觉紧迫的事，或许并没有看起来那么紧迫。"},
    "INS12": {"en": "You tend to take on more than necessary — today shows it.", "zh": "你常常揽下超出必要的责任——今天正是如此。"},
    "INS13": {"en": "You've been moving fast enough to lose your footing a little.", "zh": "你一直走得很快，以至于有些站不稳脚跟。"},
    "INS14": {"en": "Feeling untethered is a sign to return to something familiar.", "zh": "漂浮不定时，是时候回到熟悉的事物中去。"},
    "INS15": {"en": "Small routines matter more than big plans when you feel ungrounded.", "zh": "当你感到不踏实时，小小的日常习惯比宏大计划更重要。"},
    "INS16": {"en": "Reconnecting with your body can help more than thinking your way through.", "zh": "重新连结身体，往往比一味思考更有帮助。"},
    "INS17": {"en": "You're in a steady place across the board — a good moment to build.", "zh": "你目前整体处于稳定状态——正是建设的好时机。"},
    "INS18": {"en": "Nothing urgent stands out today; that itself is worth noticing.", "zh": "今天没有特别紧迫的事，这本身就值得留意。"},
    "INS19": {"en": "Steadiness like this is a good time to invest in what matters.", "zh": "这样的平稳，正适合投入到真正重要的事情上。"},
    "INS20": {"en": "You have more capacity than usual — use it intentionally.", "zh": "你现在的余力比平时更多——不妨有意地善用它。"},
}

# Which insight ids are candidates for a given resolve_focus_key() result —
# insight is meant to name something specific about the numbers, so unlike
# the other two libraries it's grounded by focus rather than fully generic.
INSIGHT_IDS_BY_FOCUS = {
    "emotional_energy": ["INS01", "INS02", "INS03", "INS04"],
    "mental_clarity": ["INS05", "INS06", "INS07", "INS08"],
    "inner_pressure": ["INS09", "INS10", "INS11", "INS12"],
    "grounding": ["INS13", "INS14", "INS15", "INS16"],
    "balanced": ["INS17", "INS18", "INS19", "INS20"],
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
        "key": "scarlet", "name": "Scarlet", "name_zh": "赤红", "swatch": "#c0392b",
        "traits": ["Vitality", "Passion", "Courage"],
        "description": "A bold, energising red that awakens motivation and physical vitality.",
        "article": "Scarlet is the colour of movement — it's what the body reaches for when energy is running low and momentum needs a spark. It's associated with vitality, passion and courage: not recklessness, but the willingness to act on what matters.",
        "benefit": "You may benefit from more energy, motivation and a spark of courage.",
        "affirmations": ["I welcome energy and momentum back into my day.", "I act with courage, even in small steps."],
        "positive_traits": ["Energised", "Bold", "Passionate", "Decisive", "Alive"],
        "negative_traits": ["Impulsive", "Restless", "Impatient", "Quick-tempered", "Overextended"],
    },
    "russet": {
        "key": "russet", "name": "Russet", "name_zh": "赭红", "swatch": "#8b4a2b",
        "traits": ["Stability", "Warmth", "Resilience"],
        "description": "A warm, earthy brown-red that steadies you and restores a sense of resilience.",
        "article": "Russet is the colour of solid ground — the warm brown-red of autumn leaves and turned soil. It carries stability rather than urgency, built slowly through repetition rather than a single grand gesture.",
        "benefit": "You may benefit from more stability, warmth and steady resilience.",
        "affirmations": ["I am steady, even when the ground feels uncertain.", "I build resilience one grounded step at a time."],
        "positive_traits": ["Steady", "Warm", "Resilient", "Reliable", "Patient"],
        "negative_traits": ["Stubborn", "Slow to change", "Guarded", "Overcautious", "Rigid"],
    },
    "gold": {
        "key": "gold", "name": "Gold", "name_zh": "金黄", "swatch": "#b9902a",
        "traits": ["Confidence", "Abundance", "Radiance"],
        "description": "A warm, radiant gold that reflects confidence and sustained, balanced progress.",
        "article": "Gold is the colour of quiet achievement — not the loud win, but the steady accumulation of effort that's finally visible. It asks you to notice what's already working rather than chase more.",
        "benefit": "You may benefit from recognising your own progress and letting it build quiet confidence.",
        "affirmations": ["I trust the progress I've already made.", "I let my steady effort shine."],
        "positive_traits": ["Confident", "Radiant", "Generous", "Optimistic", "Accomplished"],
        "negative_traits": ["Complacent", "Overconfident", "Showy", "Entitled", "Coasting"],
    },
    "forest": {
        "key": "forest", "name": "Forest", "name_zh": "森绿", "swatch": "#4a6b3d",
        "traits": ["Grounding", "Growth", "Renewal"],
        "description": "A deep, grounding green that supports steadiness, emotional recovery and sustainable growth.",
        "article": "Forest is the colour of steady, unhurried growth — the deep green of old trees rather than a new sprout. Especially supportive when pressure has been building: it asks you to root down, not push harder.",
        "benefit": "You may benefit from more grounding, balance and emotional recovery.",
        "affirmations": ["I choose steady progress over unnecessary rush.", "I create space to grow with clarity and calm."],
        "positive_traits": ["Grounded", "Balanced", "Nurturing", "Renewing", "Patient"],
        "negative_traits": ["Withdrawn", "Overcommitted", "Depleted", "Avoidant", "Slow to ask for help"],
    },
    "ocean": {
        "key": "ocean", "name": "Ocean", "name_zh": "海蓝", "swatch": "#3f8f8a",
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
    "Rebuilding energy": {"colour_key": "scarlet", "tags": ["energy", "lift"], "routine": "A 10-minute walk before noon, away from screens.", "routine_zh": "中午前进行10分钟散步，远离屏幕。"},
    "Finding clarity": {"colour_key": "ocean", "tags": ["clarity", "focus"], "routine": "Write down the one thing that matters most today, before anything else.", "routine_zh": "先写下今天最重要的一件事，再做其他事情。"},
    "Releasing pressure": {"colour_key": "forest", "tags": ["release", "calm"], "routine": "Set a 15-minute timer to do nothing but breathe and let your shoulders drop.", "routine_zh": "设定15分钟计时器，只专注呼吸，让肩膀放松下沉。"},
    "Regaining grounding": {"colour_key": "russet", "tags": ["grounding", "steadiness"], "routine": "Stand barefoot for two minutes and name five things you can feel.", "routine_zh": "赤脚站立两分钟，说出五件你能感觉到的事物。"},
    "Sustaining balance": {"colour_key": "gold", "tags": ["calm", "reflection"], "routine": "Keep doing what's working — a short reflection tonight will reinforce it.", "routine_zh": "继续做有效的事——今晚简短反思会强化它。"},
}

# Deterministic "material affinity" — same spirit as FOCUS_TO_COLOUR above
# (flavour, not a real mineralogical claim): which of the vendor catalog's
# 3 real stone types (confirmed against the live API — Crystal/Nephrite/
# Jade are the *only* `type` values that exist in it) pairs with each
# focus. Crystal for the two "activating" focuses, Jade for the two
# "settling" ones, Nephrite for steady balance. Feeds the vendor fetch's
# `type=` filter (app/services/product_api.py) and the "Material Affinity"
# key-info on the recommendation detail page.
FOCUS_TO_MATERIAL = {
    "Rebuilding energy": "Crystal",
    "Finding clarity": "Crystal",
    "Releasing pressure": "Jade",
    "Regaining grounding": "Jade",
    "Sustaining balance": "Nephrite",
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

JOURNAL_MOODS = [
    "Calm", "Hopeful", "Tired", "Anxious", "Grateful", "Content", "Overwhelmed", "Energised",
    "Frustrated", "Sad", "Peaceful", "Excited",
]
JOURNAL_THEMES = [
    "Growth", "Responsibility", "Relationships", "Self-Care", "Work", "Clarity", "Rest", "Gratitude",
    "Health", "Creativity", "Family", "Identity",
]


def truncate_words(text: str, limit: int = 100) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]) + "…"
