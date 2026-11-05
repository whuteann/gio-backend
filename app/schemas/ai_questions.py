from pydantic import BaseModel

from app.schemas.common import LocalizedText


class CheckInQuestionSetGeneration(BaseModel):
    """text_format for the check-in question-generation call — see
    docs/behaviour_log_0006.md Phase 2 and gio-member-app/docs/
    behaviour_log_0002.md. One field per pillar, not a list: the schema
    itself enforces exactly one question per dimension, in a fixed order,
    rather than trusting a list's length/contents. Every language at once, since
    this set is shared/cached across every user for the day regardless of
    their language (docs/behaviour_log_0002.md) — generating them together
    once is cheaper than generating per-language sets.
    """

    emotional_energy: LocalizedText
    mental_clarity: LocalizedText
    inner_pressure: LocalizedText
    grounding: LocalizedText


class InnerReadingQuestionSetGeneration(BaseModel):
    """text_format for the Inner Reading question-generation call — see
    docs/behaviour_log_0007.md Phase 2. Same fixed-field-per-pillar
    principle as CheckInQuestionSetGeneration, doubled: 2 questions per
    pillar (8 total), named rather than a validated list.
    """

    emotional_energy_1: LocalizedText
    emotional_energy_2: LocalizedText
    mental_clarity_1: LocalizedText
    mental_clarity_2: LocalizedText
    inner_pressure_1: LocalizedText
    inner_pressure_2: LocalizedText
    grounding_1: LocalizedText
    grounding_2: LocalizedText
