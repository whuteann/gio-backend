"""Journal mood/theme tagging + insights — a Python port of
gio-member-app/lib/journal.ts.
"""

from collections import Counter
from datetime import date as date_type, timedelta

from app.models.journal import JournalEntry
from app.services.content import JOURNAL_MOODS, JOURNAL_THEMES
from app.services.gamification import week_start
from app.services.scoring import pick_phrasing


def tag_journal_entry(entry_id: str) -> tuple[str, str]:
    mood = pick_phrasing(f"{entry_id}-mood", JOURNAL_MOODS)
    theme = pick_phrasing(f"{entry_id}-theme", JOURNAL_THEMES)
    return mood, theme


def _most_common(values: list[str]) -> str | None:
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]


def build_journal_insights(entries: list[JournalEntry], today: date_type) -> dict:
    this_week_start = week_start(today)
    prior_week_start = this_week_start - timedelta(days=7)

    this_week = [e for e in entries if week_start(e.created_at.date()) == this_week_start]
    prior_week = [e for e in entries if week_start(e.created_at.date()) == prior_week_start]

    return {
        "entries_this_week": len(this_week),
        "entries_delta": len(this_week) - len(prior_week),
        "top_mood": _most_common([e.mood for e in this_week]),
        "top_theme": _most_common([e.theme for e in this_week]),
    }
