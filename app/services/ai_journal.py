"""AI mood/theme classification for journal entries — replaces the old
`tag_journal_entry` (app/services/journal.py), which picked a mood/theme by
hashing the entry's own random id and never looked at its content at all.

Same "constrained selection" mechanism as AffirmationId/InsightId/
ReflectionQuestionId (app/schemas/ai_outcome.py): a static Enum built from
the fixed JOURNAL_MOODS/JOURNAL_THEMES lists at import time, so the model
is structurally incapable of returning a mood/theme outside the closed
set — pills stay translatable (app/.../moods.*, themes.* i18n keys) and
aggregable (Counter-based "most common" insight) exactly as before, only
now genuinely grounded in what was written.
"""

from enum import Enum

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings
from app.services.content import JOURNAL_MOODS, JOURNAL_THEMES

_client = AsyncOpenAI(api_key=settings.openai_api_key)

_SYSTEM_MESSAGE = (
    "You are a precise emotional-content classifier for a wellness journal. "
    "You must strictly follow the required JSON structure."
)

MoodId = Enum("MoodId", {m: m for m in JOURNAL_MOODS})
ThemeId = Enum("ThemeId", {t: t for t in JOURNAL_THEMES})


class JournalTagging(BaseModel):
    mood: MoodId
    theme: ThemeId


async def classify_journal_entry(content: str) -> tuple[str, str]:
    """Picks exactly one mood and one theme from the closed lists above,
    grounded in `content`. Raises on API failure/timeout — the caller
    (app/api/v1/endpoints/journal.py) is responsible for falling back to
    the old deterministic tagging rather than blocking the save."""
    prompt = f"""\
A user wrote this journal entry:
\"\"\"
{content}
\"\"\"

Classify it:
- mood: the single mood from the allowed list that most specifically
  matches how they actually sound in this entry — not a safe default
  every time, and not the most positive-sounding option just to be kind.
- theme: the single theme from the allowed list that most specifically
  matches what this entry is actually about.
"""

    response = await _client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": _SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ],
        text_format=JournalTagging,
    )
    parsed = response.output_parsed
    return parsed.mood.value, parsed.theme.value
