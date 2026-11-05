"""The languages this app supports, in one place.

Before this module the set of languages was implied in five scattered
places — two `{"en": "zh", "zh": "en"}` maps, two `in ("en", "zh")` gates
and a `LANGUAGE_NAMES` dict. Each of them silently downgraded anything else
to English: no error, no log, just the wrong language. Adding a third
language means those can no longer be written inline anywhere.

The storage convention these support: English lives in the unsuffixed
column, other languages in `<field>_<code>` (see
services/reading_language.py). `column_suffix` is the only place that
mapping is expressed.
"""

SUPPORTED: tuple[str, ...] = ("en", "zh", "ms")
DEFAULT = "en"

# What the model is told to write in. Names, not codes — a code in a prompt
# is a guess the model has to make.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "zh": "Chinese (Simplified)",
    "ms": "Malay (Bahasa Melayu)",
}


def normalize(language: str | None) -> str:
    """A supported code, or English. Use at every boundary where a language
    arrives from outside — a request body, a stored preference — so an
    unknown value fails over predictably instead of reaching the database."""
    return language if language in SUPPORTED else DEFAULT


def others(language: str) -> list[str]:
    """Every supported language except this one.

    Replaces the old OTHER_LANGUAGE maps, which encoded "the one other
    language" — a concept that stopped existing at three. Callers queue one
    background generation per entry, so this returning two instead of one
    is what makes the second pass happen.
    """
    primary = normalize(language)
    return [code for code in SUPPORTED if code != primary]


def column_suffix(language: str) -> str:
    """`""` for English, `"_zh"` / `"_ms"` otherwise — English has no
    suffix because it occupies the original column (CheckInSession's
    convention, which InnerReading and the recommendation tables follow)."""
    code = normalize(language)
    return "" if code == DEFAULT else f"_{code}"


def language_name(language: str) -> str:
    return LANGUAGE_NAMES.get(normalize(language), LANGUAGE_NAMES[DEFAULT])


def fallback_chain(requested: str, preferred: str | None = None) -> list[str]:
    """Which languages to try, in order: what was asked for, then the
    account's own preference, then English. Never returns an empty list, so
    a caller can always render something rather than a blank card."""
    chain: list[str] = []
    for code in (requested, preferred, DEFAULT):
        norm = normalize(code) if code else None
        if norm and norm not in chain:
            chain.append(norm)
    return chain


def record_ready(current: list[str] | None, language: str) -> tuple[list[str], str]:
    """`(languages_ready, generation_status)` after `language` finishes.

    With two languages one background pass meant "done", so the pass could
    just set READY. With three there are two passes, and whichever finished
    first would have marked a row complete while a language was still
    missing — a Malay reader would be told the content was ready and shown
    a fallback. So READY now means "every language in SUPPORTED is present",
    and `languages_ready` carries which ones actually are.

    Idempotent and order-independent: re-running a pass that already
    succeeded changes nothing, and the result is always in SUPPORTED order
    regardless of which pass landed first.
    """
    ready = {normalize(code) for code in (current or [])} | {normalize(language)}
    ordered = [code for code in SUPPORTED if code in ready]
    return ordered, ("READY" if len(ordered) == len(SUPPORTED) else "PARTIAL")
