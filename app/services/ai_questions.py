"""AI-generated Emotional Check-In questions.

Same principle as app/services/ai_personality.py: the model's job is the
question text only. It never sees or produces any numbers — no scoring,
no scale values beyond being told the answer format is 1-5. Results
parsing (app/services/scoring.py) stays entirely deterministic, trusting
only the fixed `dimension` key each question is generated under, exactly
per docs/behaviour_log_0006.md's "AI is responsible for question
generation ONLY."

Bilingual since gio-member-app/docs/behaviour_log_0002.md: each question
comes back written in both English and Chinese in the same call (not a
translation of one into the other), so the one shared/cached set still
serves every user regardless of their language — no extra generation
cost, just a slightly larger response.
"""

from openai import AsyncOpenAI

from app.config import settings
from app.schemas.ai_questions import CheckInQuestionSetGeneration, InnerReadingQuestionSetGeneration

_client = AsyncOpenAI(api_key=settings.openai_api_key)

_SYSTEM_MESSAGE = (
    "You are a clear, direct wellness check-in writer for an app called Auren. "
    "You write short, plain questions that ask how the user feels right now — no invented scenarios, no metaphors, just one direct question per dimension. "
    "You must strictly follow the required JSON structure."
)

_PROMPT = """\
Generate a set of 4 short, direct questions that ask how the user feels \
right now, one per pillar below, in order. Each expects a 1-5 self-rating \
as its answer.

The 4 Pillars:
- emotional_energy: Emotional Energy (Drained -> Energised)
- mental_clarity: Mental Clarity (Foggy -> Clear)
- inner_pressure: Inner Pressure (Light -> Heavy)
- grounding: Grounding (Unsteady -> Rooted)

HOW TO WRITE EACH QUESTION:
Ask plainly and directly about the present moment — no invented \
situation, no metaphor or imagery, no scene to set up first. Just a \
short, clear question about how the user currently feels along that \
pillar's spectrum. For example, a direct question for emotional_energy \
could simply be: "Right now, how would you describe your energy?" / \
"此刻，你感觉自己的精力如何？" — that plain, direct register is the target for \
every pillar, not just this example.

VOICE & CRAFT:
- Short: a single plain sentence, roughly 6-14 words.
- Consistent over novel: favor predictable, familiar wording across \
questions and across calls — a user should recognize the shape of these \
questions each time, not be surprised by them. Do not strain for a fresh \
angle or a clever turn of phrase.
- Plain and natural in both English and Chinese — not a literal, \
word-for-word translation of one into the other, but the same plain, \
direct register in each.
- No invented situations, no metaphor, no imagery, no scene-setting. Ask \
about the feeling itself, directly.

Output rules:
- One question per pillar, a single natural sentence ending in a \
question mark.
- The question should clearly invite a 1-5 self-rating along that \
pillar's named spectrum (e.g. the emotional_energy question should read \
naturally whether the honest answer is "drained" or "energised") — do \
not mention the number scale explicitly, the UI shows the 1-5 scale \
separately.
- Do not ask about any pillar other than the one named for that field.
- Plain text only, no markdown, no numbering, no emoji.
- Write each question in both English (`en`) and Chinese (`zh`).
"""


async def generate_checkin_questions() -> CheckInQuestionSetGeneration:
    response = await _client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": _SYSTEM_MESSAGE},
            {"role": "user", "content": _PROMPT},
        ],
        text_format=CheckInQuestionSetGeneration,
        reasoning={"effort": "medium"},
        # No `temperature` — see app/services/ai_personality.py's note on
        # the configured model rejecting that parameter.
    )
    return response.output_parsed


# Inner Reading — see docs/behaviour_log_0007.md Phase 2 and
# gio-backend/docs/behaviour_log_0013.md. Same contract as check-in's
# questions above (question text only, no numbers), doubled to 2
# questions per pillar — but a deliberately different *voice* from
# check-in's, per direct product direction: check-in lives in small,
# ordinary moments; Inner Reading lives in reflection and planning, for
# someone thinking and creating their way through a real challenge. Its
# own system message (below) reinforces that register on top of the
# prompt itself.
_READING_SYSTEM_MESSAGE = (
    "You are a clear, direct guide designing a deeper reflective practice — an \"Inner Reading\" — for an app called Auren. "
    "You write short, plain questions that ask how the user currently feels and how they expect to move forward — no invented scenarios, no metaphors, just direct questions per dimension. "
    "You must strictly follow the required JSON structure."
)

_READING_PROMPT = """\
Generate a set of 8 short, direct questions (2 per pillar) for a deeper \
reflective practice called an "Inner Reading". Evaluate the user's \
current state across these 4 pillars, in order. Each question expects a \
1-5 self-rating as its answer.

The 4 Pillars:
- emotional_energy: Emotional Energy (Drained -> Energised)
- mental_clarity: Mental Clarity (Foggy -> Clear)
- inner_pressure: Inner Pressure (Light -> Heavy)
- grounding: Grounding (Unsteady -> Rooted)

HOW TO WRITE EACH PAIR:
Ask plainly and directly — no invented scenario, no metaphor, no \
imagery, no scene to set up first. For each pillar, the FIRST question \
asks directly how the user currently feels along that pillar's spectrum \
right now; the SECOND asks directly how they expect to feel or move on \
that pillar going forward. Both are plain, direct questions about the \
feeling and the path ahead — not a story about either.

VOICE & CRAFT:
- Short: a single plain sentence per question, roughly 8-16 words.
- Consistent over novel: favor predictable, familiar wording across \
questions and across calls — a user should recognize the shape of these \
questions each time, not be surprised by them. Do not strain for a fresh \
angle, a clever turn of phrase, or a new metaphor.
- Plain and natural in both English and Chinese — not a literal, \
word-for-word translation of one into the other, but the same plain, \
direct register in each.
- No invented situations, no metaphor or imagery (no compass, current, \
threshold, horizon, etc.) — ask about the feeling and the path forward \
directly.

Output rules:
- Two questions per pillar, each a single natural sentence ending in a \
question mark, and the two must be meaningfully different from each \
other (current state vs. looking ahead) — not near-duplicates.
- The question should clearly invite a 1-5 self-rating along that \
pillar's named spectrum — do not mention the number scale explicitly, \
the UI shows the 1-5 scale separately.
- Do not ask about any pillar other than the one named for that field.
- Plain text only, no markdown, no numbering, no emoji.
- Write each question in both English (`en`) and Chinese (`zh`).
"""


async def generate_reading_questions() -> InnerReadingQuestionSetGeneration:
    response = await _client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": _READING_SYSTEM_MESSAGE},
            {"role": "user", "content": _READING_PROMPT},
        ],
        text_format=InnerReadingQuestionSetGeneration,
        reasoning={"effort": "medium"},
        # No `temperature` — see app/services/ai_personality.py's note on
        # the configured model rejecting that parameter.
    )
    return response.output_parsed
