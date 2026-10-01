from pydantic import BaseModel

from app.schemas.common import BilingualText


class CheckInQuestionSetGeneration(BaseModel):
    """text_format for the check-in question-generation call — see
    docs/behaviour_log_0006.md Phase 2 and gio-member-app/docs/
    behaviour_log_0002.md. One field per pillar, not a list: the schema
    itself enforces exactly one question per dimension, in a fixed order,
    rather than trusting a list's length/contents. Bilingual since this
    set is shared/cached across every user for the day regardless of
    their language (docs/behaviour_log_0002.md) — generating both once is
    cheaper than generating per-language sets.
    """

    emotional_energy: BilingualText
    mental_clarity: BilingualText
    inner_pressure: BilingualText
    grounding: BilingualText


class InnerReadingQuestionSetGeneration(BaseModel):
    """text_format for the Inner Reading question-generation call — see
    docs/behaviour_log_0007.md Phase 2. Same fixed-field-per-pillar
    principle as CheckInQuestionSetGeneration, doubled: 2 questions per
    pillar (8 total), named rather than a validated list.
    """

    emotional_energy_1: BilingualText
    emotional_energy_2: BilingualText
    mental_clarity_1: BilingualText
    mental_clarity_2: BilingualText
    inner_pressure_1: BilingualText
    inner_pressure_2: BilingualText
    grounding_1: BilingualText
    grounding_2: BilingualText
