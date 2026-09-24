from pydantic import BaseModel


class CheckInQuestionSetGeneration(BaseModel):
    """text_format for the check-in question-generation call — see
    docs/behaviour_log_0006.md Phase 2. One field per pillar, not a list:
    the schema itself enforces exactly one question per dimension, in a
    fixed order, rather than trusting a list's length/contents.
    """

    emotional_energy: str
    mental_clarity: str
    inner_pressure: str
    grounding: str


class InnerReadingQuestionSetGeneration(BaseModel):
    """text_format for the Inner Reading question-generation call — see
    docs/behaviour_log_0007.md Phase 2. Same fixed-field-per-pillar
    principle as CheckInQuestionSetGeneration, doubled: 2 questions per
    pillar (8 total), named rather than a validated list.
    """

    emotional_energy_1: str
    emotional_energy_2: str
    mental_clarity_1: str
    mental_clarity_2: str
    inner_pressure_1: str
    inner_pressure_2: str
    grounding_1: str
    grounding_2: str
