from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OnboardingRequest(BaseModel):
    birthdate: str  # YYYY-MM-DD


class BaselineAnswer(BaseModel):
    index: int
    choice: str  # "A" | "B"


class RecalibrateRequest(BaseModel):
    answers: list[BaselineAnswer]


class CorePersonalityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    archetype: str
    icon: str
    thinking: int
    emotional_sensitivity: int
    adaptability: int
    willpower: int
    overall_explanation: str
    pillar_explanations: dict
    assessment_version: str
    is_current: bool
    generated_at: datetime
    recalibrated_at: datetime | None


class BaselineOptionOut(BaseModel):
    label: str


class BaselineQuestionOut(BaseModel):
    index: int
    pillar: str
    prompt: str
    option_a: BaselineOptionOut
    option_b: BaselineOptionOut


class RecalibrateResponse(BaseModel):
    ok: bool
    personality: CorePersonalityOut | None = None
    next_eligible_at: datetime | None = None


class NumerologyOut(BaseModel):
    life_path_number: int
    birthday_number: int
    talent_number: int


class ColourAffinityOut(BaseModel):
    colour_key: str
    score: int


class ColourBreakdownOut(BaseModel):
    dominant_colour_key: str
    scores: list[ColourAffinityOut]
