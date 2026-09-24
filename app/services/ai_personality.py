"""AI-generated Core Personality narrative content.

Same principle as sample-logic.py and docs/behaviour_log_0001.md: every
number is computed deterministically in app/services/numerology.py *before*
this is ever called, and handed to the model as a fixed fact it's told not
to recalculate. The model's only job is the narrative wrapped around those
numbers. Unlike sample-logic.py's BilingualElementalCalculation, generation
here is single-language per call — see docs behaviour log for why (dual-
language is sequential: generate the requested language, return, generate
the other one after, not both in one blocking call).
"""

from openai import AsyncOpenAI

from app.config import settings
from app.schemas.ai_personality import CorePersonalityGeneration

LANGUAGE_NAMES = {"en": "English", "zh": "Chinese (Simplified)"}

_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def generate_core_personality_content(
    *,
    birthdate: str,
    birthday_number: int,
    life_path_number: int,
    talent_number: str,
    colour_weights: dict[str, int],
    language: str,
) -> CorePersonalityGeneration:
    language_name = LANGUAGE_NAMES.get(language, "English")

    system_message = (
        "You are a warm, insightful numerology and personality expert writing for a "
        "wellness app called Gio. You must strictly follow the required JSON structure."
    )

    prompt = f"""
A user's date of birth is {birthdate}.

IMPORTANT: the following values have already been computed by code. Do NOT
recalculate or alter them — use them exactly as given as the grounding for
your interpretation:
- Birthday Number: {birthday_number}
- Life Path Number: {life_path_number}
- Talent Number: {talent_number}
- Colour affinity weights (0-30 each, already computed):
  * Scarlet: {colour_weights.get("scarlet", 0)}
  * Russet: {colour_weights.get("russet", 0)}
  * Gold: {colour_weights.get("gold", 0)}
  * Forest: {colour_weights.get("forest", 0)}
  * Ocean: {colour_weights.get("ocean", 0)}

Write the following, entirely in {language_name}:
- title: a short, evocative archetype-style label for this person's core
  identity (2-4 words), in the spirit of a name like "The Open Horizon" —
  not literally that phrase, something fresh grounded in the numbers above.
- subtitle: one short line elaborating on the title (under 12 words).
- overview: a warm, specific 2-3 sentence description of who this person
  is at their core, grounded in the Birthday/Life Path/Talent Number
  pattern above — not generic personality-quiz language.
- birthday_number_content: 2-3 sentences interpreting the Birthday Number
  specifically.
- life_path_number_content: 2-3 sentences interpreting the Life Path
  Number specifically.
- talent_number_content: 2-3 sentences interpreting the Talent Number
  specifically — natural gifts and potential blind spots, framed as
  tendencies, not fixed traits.
- summary: NOT user-facing. A concise (2-3 sentence) factual grounding
  summary of this person's core identity, written to be consumed by another
  AI step downstream that will use it to choose a supportive colour and
  product recommendations. Plain, dense, no flourishes.

Output rules:
- Return only the fields defined by the response schema.
- Every field is a plain string (not markdown, no bullet points).
- Write naturally in {language_name} — do not translate word-for-word from
  English if English is not the target language.
"""

    response = await _client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        text_format=CorePersonalityGeneration,
        # No `temperature` — the configured model (see OPENAI_MODEL) is a
        # newer reasoning-style model that rejects it (400: "Unsupported
        # parameter: 'temperature' is not supported with this model"),
        # unlike sample-logic.py's target model which accepted it.
    )
    return response.output_parsed
