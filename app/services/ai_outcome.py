"""AI-generated Emotional Check-In outcome — the six Inner State narrative
fields plus a short memory summary for Narrative.

Same principle as every other AI service in this app: the deterministic
pillar values and the resolved focus key are computed first
(app/services/scoring.py) and handed to the model as fixed facts. The
model's only job is writing grounded narrative around them, plus a short
system-memory summary of this specific event — never the numbers
themselves. Grounded on the user's own recent NarrativeEntry history (see
docs/behaviour_log_0005.md/0006.md) so this isn't a cold, context-free
generation each time.

English-only for now — check-in questions (Phase 2) are English-only for
the same reason (the app doesn't yet ask for bilingual check-in content);
revisit together if that changes.
"""

from openai import AsyncOpenAI

from app.config import settings
from app.schemas.ai_outcome import CheckInOutcomeGeneration, InnerReadingOutcomeGeneration

_client = AsyncOpenAI(api_key=settings.openai_api_key)

_SYSTEM_MESSAGE = (
    "You are a warm, perceptive wellness companion writing for an app called Gio. "
    "You must strictly follow the required JSON structure."
)


async def generate_checkin_outcome(
    *,
    dims: dict[str, int],
    focus_label: str,
    recent_narrative_summaries: list[str],
) -> CheckInOutcomeGeneration:
    if recent_narrative_summaries:
        memory_block = "\n".join(f"- {s}" for s in recent_narrative_summaries)
    else:
        memory_block = "(none yet — this is the first recorded check-in or reading for this user)"

    prompt = f"""\
A user just completed an emotional check-in.

IMPORTANT: the following values have already been computed by code. Do NOT
recalculate or alter them — use them exactly as given as the grounding for
your writing:
- Emotional Energy: {dims["emotional_energy"]}/100
- Mental Clarity: {dims["mental_clarity"]}/100
- Inner Pressure: {dims["inner_pressure"]}/100
- Grounding: {dims["grounding"]}/100
- Current focus (already determined): {focus_label}

Recent memory of this user's last check-ins/readings, oldest to newest
(use this for continuity — do not contradict it, and reference a pattern
across entries if one is genuinely present, but don't force a connection
that isn't there):
{memory_block}

Write the following, entirely in English:
- insight: 1-2 sentences naming what today's numbers suggest, specific to
  this moment.
- reflection_question: one open question inviting the user to reflect
  further, connected to the insight above.
- reminder: one short, warm reminder for the user to carry with them today.
- current_focus: a short (2-5 word) phrase naming the user's ongoing
  journey right now, in the spirit of "{focus_label}" but written as
  natural, personal phrasing rather than repeating that label verbatim.
- friendly_advice: one concrete, small, doable suggestion for today.
- affirmation: one first-person affirmation statement.
- narrative_summary: NOT user-facing. A factual, third-person summary of
  this check-in in 20 words or fewer, written to be read back as memory
  context for a *future* generation like this one — plain and dense, no
  flourishes, no direct address to the user.

Output rules:
- Every field is a plain string (no markdown, no bullet points).
- Keep each field genuinely short — this is a daily check-in, not an
  essay.
"""

    response = await _client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": _SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ],
        text_format=CheckInOutcomeGeneration,
        # No `temperature` — see app/services/ai_personality.py's note on
        # the configured model rejecting that parameter.
    )
    return response.output_parsed


# Inner Reading — see docs/behaviour_log_0007.md Phase 4. Same grounding
# principle as check-in's outcome above (dims + focus already computed in
# code, recent NarrativeEntry history for continuity), extended with Inner
# Reading's own record content (narrative/title/subtitle) and the 4
# life-area fields, all in the one call rather than a second round trip.
async def generate_reading_outcome(
    *,
    dims: dict[str, int],
    focus_label: str,
    recent_narrative_summaries: list[str],
) -> InnerReadingOutcomeGeneration:
    if recent_narrative_summaries:
        memory_block = "\n".join(f"- {s}" for s in recent_narrative_summaries)
    else:
        memory_block = "(none yet — this is the first recorded check-in or reading for this user)"

    prompt = f"""\
A user just completed an Inner Reading — a slower, more considered \
reflective practice than a daily check-in.

IMPORTANT: the following values have already been computed by code. Do NOT
recalculate or alter them — use them exactly as given as the grounding for
your writing:
- Emotional Energy: {dims["emotional_energy"]}/100
- Mental Clarity: {dims["mental_clarity"]}/100
- Inner Pressure: {dims["inner_pressure"]}/100
- Grounding: {dims["grounding"]}/100
- Current focus (already determined): {focus_label}

Recent memory of this user's last check-ins/readings, oldest to newest
(use this for continuity — do not contradict it, and reference a pattern
across entries if one is genuinely present, but don't force a connection
that isn't there):
{memory_block}

Write the following, entirely in English:
- insight: 1-2 sentences naming what today's numbers suggest, specific to
  this moment.
- reflection_question: one open question inviting the user to reflect
  further, connected to the insight above.
- reminder: one short, warm reminder for the user to carry with them today.
- current_focus: a short (2-5 word) phrase naming the user's ongoing
  journey right now, in the spirit of "{focus_label}" but written as
  natural, personal phrasing rather than repeating that label verbatim.
- friendly_advice: one concrete, small, doable suggestion for today.
- affirmation: one first-person affirmation statement.
- narrative_summary: NOT user-facing. A factual, third-person summary of
  this reading in 20 words or fewer, written to be read back as memory
  context for a *future* generation like this one — plain and dense, no
  flourishes, no direct address to the user.
- narrative: a fuller, 3-5 sentence reflective read of this moment — this
  is the main body of the reading, more depth than the single-insight
  fields above, in a warm second-person voice.
- title: a short (2-5 word) headline for this reading.
- subtitle: one sentence expanding on the title.
- life_area_work, life_area_relationships, life_area_personal_growth,
  life_area_conflict_management: one short, concrete paragraph each,
  translating this reading into a specific implication for that life
  area — practical, not generic filler.

Output rules:
- Every field is a plain string (no markdown, no bullet points).
- insight/reflection_question/reminder/current_focus/friendly_advice/
  affirmation/narrative_summary stay genuinely short, matching a daily
  check-in's brevity — narrative, title, subtitle, and the 4 life_area_*
  fields are where this reading's extra depth belongs.
"""

    response = await _client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": _SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ],
        text_format=InnerReadingOutcomeGeneration,
        # No `temperature` — see app/services/ai_personality.py's note on
        # the configured model rejecting that parameter.
    )
    return response.output_parsed
