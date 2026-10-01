from pydantic import BaseModel


class BilingualText(BaseModel):
    """One generated string, in both languages — the model writes each
    language directly rather than one being a translation of the other.
    Shared by every AI schema that needs a genuinely bilingual field (see
    gio-member-app/docs/behaviour_log_0002.md)."""

    en: str
    zh: str


class NumberPoint(BaseModel):
    """One short, emoji-led highlight — the point-form replacement for a
    numerology number's old paragraph-style interpretation (see
    app/services/ai_personality.py). `emoji` is its own field, not prefixed
    onto `text`, so the frontend never has to parse/strip it back out."""

    emoji: str
    text: str
