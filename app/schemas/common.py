from pydantic import BaseModel


class LocalizedText(BaseModel):
    """One generated string, in every supported language — the model writes
    each language directly rather than one being a translation of the other.
    Shared by every AI schema whose field is cheap enough to generate in all
    languages on the blocking call (see gio-member-app/docs/
    behaviour_log_0002.md). Was BilingualText; renamed when Malay landed,
    since the field count now follows services/languages.SUPPORTED and the
    old name would have to be re-read as "three" to stay true.

    Heavy fields (Inner Reading's narrative, Core Personality's overview) do
    NOT use this — they generate one language per call and fill the rest from
    a BackgroundTask, which is why those live in per-language columns
    instead."""

    en: str
    zh: str
    ms: str


class NumberPoint(BaseModel):
    """One short, emoji-led highlight — the point-form replacement for a
    numerology number's old paragraph-style interpretation (see
    app/services/ai_personality.py). `emoji` is its own field, not prefixed
    onto `text`, so the frontend never has to parse/strip it back out."""

    emoji: str
    text: str
