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

Affirmation/insight/reflection_question are no longer free-written — the
model *selects* an id from the curated library (content.py, see
docs/behaviour_log_0011.md), grounded on the same inputs as before.
current_focus/friendly_advice/reminder (and check-in's title/subtitle)
stay freely generated, and are now genuinely bilingual — written directly
in both languages in the same call, per
gio-member-app/docs/behaviour_log_0002.md — since their target columns
(InnerStateSnapshot's JSONB fields) already support it.
narrative_summary stays English-only deliberately: it's system memory
(NarrativeEntry.summary), never shown to a user. Inner Reading's own
record fields (narrative/title/subtitle/life_area_*) also stay
English-only for now — `InnerReading`'s columns aren't migrated to the
bilingual JSONB shape yet (behaviour_log_0002.md Phase E).
"""

from openai import AsyncOpenAI

from app.config import settings
from app.schemas.ai_outcome import CheckInOutcomeGeneration, InnerReadingOutcomeGeneration
from app.services.content import AFFIRMATIONS, INSIGHT_IDS_BY_FOCUS, INSIGHTS, REFLECTION_QUESTIONS

_client = AsyncOpenAI(api_key=settings.openai_api_key)

_SYSTEM_MESSAGE = (
    "You are a warm, perceptive wellness companion writing for an app called Auren. "
    "You must strictly follow the required JSON structure."
)


def _candidate_list(items: dict[str, dict[str, str]]) -> str:
    return "\n".join(f'- {item_id}: "{text["en"]}"' for item_id, text in items.items())


def _library_block(focus_key: str) -> str:
    insight_candidates = {i: INSIGHTS[i] for i in INSIGHT_IDS_BY_FOCUS[focus_key]}
    return f"""\
Choose an affirmation_id from this list (pick whichever best fits this
specific moment — do not invent a new one):
{_candidate_list(AFFIRMATIONS)}

Choose a reflection_question_id from this list, ideally one that connects
to the insight you're pointing at:
{_candidate_list(REFLECTION_QUESTIONS)}

Choose an insight_id from this list only (these are the ones that match
today's resolved focus — do not pick from outside this list):
{_candidate_list(insight_candidates)}
"""


async def generate_checkin_outcome(
    *,
    dims: dict[str, int],
    focus_label: str,
    focus_key: str,
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

{_library_block(focus_key)}

Write the following:
- affirmation_id, reflection_question_id, insight_id: as instructed above.
- reminder: one short, warm reminder for the user to carry with them today.
- current_focus: a short (2-5 word) phrase naming the user's ongoing
  journey right now, in the spirit of "{focus_label}" but written as
  natural, personal phrasing rather than repeating that label verbatim.
- friendly_advice: one concrete, small, doable suggestion for today.
- narrative_summary: NOT user-facing, English only regardless of the
  fields above. A factual, third-person summary of this check-in in 20
  words or fewer, written to be read back as memory context for a
  *future* generation like this one — plain and dense, no flourishes, no
  direct address to the user.
- title: a short (2-5 word) headline for this check-in, suitable for a
  history list (e.g. "Steady Ground", "Gentle Reset").
- subtitle: one short sentence expanding on the title.

Output rules:
- reminder, current_focus, friendly_advice, title, and subtitle are each
  written in both English (`en`) and Chinese (`zh`) — genuine, natural
  phrasing in each language, not a literal translation of one into the
  other. narrative_summary is a single plain string, English only.
- Every free-text field is plain text (no markdown, no bullet points).
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
    focus_key: str,
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

{_library_block(focus_key)}

Write the following, in English unless noted otherwise:
- affirmation_id, reflection_question_id, insight_id: as instructed above.
- reminder: one short, warm reminder for the user to carry with them today.
- current_focus: a short (2-5 word) phrase naming the user's ongoing
  journey right now, in the spirit of "{focus_label}" but written as
  natural, personal phrasing rather than repeating that label verbatim.
- friendly_advice: one concrete, small, doable suggestion for today.
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
- reminder, current_focus, and friendly_advice are each written in both
  English (`en`) and Chinese (`zh`) — genuine, natural phrasing in each
  language, not a literal translation of one into the other.
  narrative_summary, narrative, title, subtitle, and the 4 life_area_*
  fields are each a single plain string, English only, for now.
- Every free-text field is plain text (no markdown, no bullet points).
- reminder/current_focus/friendly_advice/narrative_summary stay genuinely
  short, matching a daily check-in's brevity — narrative, title, subtitle,
  and the 4 life_area_* fields are where this reading's extra depth
  belongs.
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
