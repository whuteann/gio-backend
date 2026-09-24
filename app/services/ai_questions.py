"""AI-generated Emotional Check-In questions.

Same principle as app/services/ai_personality.py: the model's job is the
question text only. It never sees or produces any numbers — no scoring,
no scale values beyond being told the answer format is 1-5. Results
parsing (app/services/scoring.py) stays entirely deterministic, trusting
only the fixed `dimension` key each question is generated under, exactly
per docs/behaviour_log_0006.md's "AI is responsible for question
generation ONLY."

English-only for now — the spec for this feature (unlike Core Personality)
doesn't ask for bilingual questions, and the whole point of this caching
scheme is one shared set reused by every user regardless of language.
"""

from openai import AsyncOpenAI

from app.config import settings
from app.schemas.ai_questions import CheckInQuestionSetGeneration, InnerReadingQuestionSetGeneration

_client = AsyncOpenAI(api_key=settings.openai_api_key)

_SYSTEM_MESSAGE = (
    "You are a thoughtful wellness check-in designer writing for an app called Gio. "
    "You must strictly follow the required JSON structure."
)

_PROMPT = """\
Generate a set of 4 questions for the purpose of evaluating the current \
inner state of the user, based on these 4 pillars, in order. Each question \
should expect a scale from 1 to 5 as its answer:

- emotional_energy: Emotional Energy (Drained -> Energised)
- mental_clarity: Mental Clarity (Foggy -> Clear)
- inner_pressure: Inner Pressure (Light -> Heavy)
- grounding: Grounding (Unsteady -> Rooted)

Output rules:
- One question per pillar, written as a single natural sentence ending in \
a question mark.
- The question should clearly invite a 1-5 self-rating along that pillar's \
named spectrum (e.g. the emotional_energy question should read naturally \
whether the honest answer is "drained" or "energised") — do not mention \
the number scale explicitly in the question text itself, the UI shows the \
1-5 scale separately.
- Do not ask about any pillar other than the one named for that field.
- Plain text only, no markdown, no numbering, no emoji.
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


# Inner Reading — see docs/behaviour_log_0007.md Phase 2. Same contract as
# check-in's questions above (question text only, no numbers), doubled to
# 2 questions per pillar, with a deeper/retrospective framing instead of
# check-in's present-moment one — Inner Reading is a slower, less frequent
# practice than a daily pulse-check.
_READING_PROMPT = """\
Generate a set of 8 questions (2 per pillar) for a deeper reflective \
practice called an "Inner Reading" — slower and more considered than a \
quick daily check-in. Evaluate the user's current inner state across \
these 4 pillars, in order. Each question should expect a scale from 1 to \
5 as its answer:

- emotional_energy: Emotional Energy (Drained -> Energised)
- mental_clarity: Mental Clarity (Foggy -> Clear)
- inner_pressure: Inner Pressure (Light -> Heavy)
- grounding: Grounding (Unsteady -> Rooted)

Output rules:
- Two questions per pillar, each a single natural sentence ending in a \
question mark, and the two questions for the same pillar must be \
meaningfully different from each other (a different angle on that \
pillar), not near-duplicates.
- Frame every question retrospectively — inviting the user to reflect \
over the last few days, not just this exact moment (e.g. "Looking back \
on the last few days..." / "...this week?" / "...lately?"), since this \
is a slower practice than a daily check-in.
- The question should clearly invite a 1-5 self-rating along that \
pillar's named spectrum — do not mention the number scale explicitly in \
the question text itself, the UI shows the 1-5 scale separately.
- Do not ask about any pillar other than the one named for that field.
- Plain text only, no markdown, no numbering, no emoji.
"""


async def generate_reading_questions() -> InnerReadingQuestionSetGeneration:
    response = await _client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": _SYSTEM_MESSAGE},
            {"role": "user", "content": _READING_PROMPT},
        ],
        text_format=InnerReadingQuestionSetGeneration,
        reasoning={"effort": "medium"},
        # No `temperature` — see app/services/ai_personality.py's note on
        # the configured model rejecting that parameter.
    )
    return response.output_parsed
