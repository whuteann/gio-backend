"""Which column holds which language for an InnerReading, and how the
second one gets filled in.

Extracted so the request path (readings.py's BackgroundTask) and the
backfill script (scripts/backfill_reading_language.py) share one definition.
Two copies of "English is the unsuffixed column, Chinese is `_zh`" is
exactly the thing that drifts.
"""

import logging

from sqlalchemy.orm import Session

from app.models.reflection import InnerReading
from app.services import languages
from app.services.ai_outcome import generate_reading_secondary_language
from app.services.scoring import focus_label_for, resolve_focus_key

logger = logging.getLogger(__name__)

def field(reading: InnerReading, name: str, language: str):
    """English lives in the unsuffixed column, other languages in
    `<name>_<code>` — the same layout CheckInSession uses, so there is no
    `_en` suffix to read. The suffix itself comes from services/languages.py
    so the convention is stated once."""
    return getattr(reading, f"{name}{languages.column_suffix(language)}", None)


def set_field(reading: InnerReading, name: str, language: str, value) -> None:
    setattr(reading, f"{name}{languages.column_suffix(language)}", value)


def localized(reading: InnerReading, name: str, requested: str, preferred: str | None = None):
    """First language in the fallback chain that actually has content.

    With two languages a simple `a ?? b` sufficed. With three, "missing"
    has to be resolved in a defined order — requested, then the account's
    preference, then English — or a Malay user with a half-generated
    reading sees a blank card instead of the English that is sitting right
    there.
    """
    for code in languages.fallback_chain(requested, preferred):
        value = field(reading, name, code)
        if value:
            return value
    return None


def dims_of(reading: InnerReading) -> dict[str, int]:
    return {
        "emotional_energy": reading.emotional_energy or 0,
        "mental_clarity": reading.mental_clarity or 0,
        "inner_pressure": reading.inner_pressure or 0,
        "grounding": reading.grounding or 0,
    }


async def fill_secondary_language(db: Session, reading: InnerReading, language: str) -> bool:
    """Generate one missing `language` for a reading that already has its
    primary, and record it. Returns True on success.

    Does not manage the session: the caller owns it, commits, and decides
    what a failure means. Raises nothing — a failed generation returns False
    and leaves the reading exactly as it was (still PARTIAL, still usable in
    its primary language, which the frontend falls back to).
    """
    primary = reading.primary_language or "en"
    dims = dims_of(reading)
    try:
        content = await generate_reading_secondary_language(
            language=language,
            dims=dims,
            focus_label=focus_label_for(resolve_focus_key(dims)),
            primary_language=primary,
            primary_narrative=field(reading, "narrative", primary) or "",
            primary_title=field(reading, "title", primary) or "",
            primary_subtitle=field(reading, "subtitle", primary) or "",
            primary_life_areas=field(reading, "life_area_insights", primary) or {},
        )
    except Exception:
        logger.exception("Inner reading %s: %s version failed to generate.", reading.id, language)
        return False

    set_field(reading, "narrative", language, content.narrative)
    set_field(reading, "title", language, content.title)
    set_field(reading, "subtitle", language, content.subtitle)
    set_field(reading, "life_area_insights", language, {
        "work": content.life_area_work,
        "relationships": content.life_area_relationships,
        "personal_growth": content.life_area_personal_growth,
        "conflict_management": content.life_area_conflict_management,
    })
    # Not a bare "READY": there are two of these passes now, and the first
    # to finish must not claim the row is complete. record_ready decides.
    reading.languages_ready, reading.generation_status = languages.record_ready(
        reading.languages_ready, language
    )
    return True
