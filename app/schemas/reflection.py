from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class QuestionOut(BaseModel):
    dimension: str
    text: str


class QuestionSetOut(BaseModel):
    blueprint_version: str
    questions: list[QuestionOut]


class AnswerIn(BaseModel):
    dimension: str
    question_text: str
    value: int  # 1-5


class CheckInSubmitRequest(BaseModel):
    answers: list[AnswerIn]
    private_note: str | None = None


class InnerReadingSubmitRequest(BaseModel):
    answers: list[AnswerIn]


class OutcomeOut(BaseModel):
    xp_awarded: int
    bonus_awarded: bool
    milestone: int | None
    new_badges: list[str]


class CheckInSubmitResponse(BaseModel):
    session_id: UUID
    outcome: OutcomeOut


class InnerReadingSubmitResponse(BaseModel):
    reading_id: UUID
    outcome: OutcomeOut


class CheckInAnswerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dimension: str
    question_text: str
    answer_value: int
    normalized_value: int
    order_index: int


class CheckInSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    blueprint_version: str
    private_note: str | None
    summary: str | None
    started_at: datetime
    completed_at: datetime | None
    answers: list[CheckInAnswerOut] = []


class InnerReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ordinal: int
    status: str
    blueprint_version: str
    emotional_energy: int | None
    mental_clarity: int | None
    inner_pressure: int | None
    grounding: int | None
    result_summary: str | None
    narrative: str | None
    insight: str | None
    reflection_question: str | None
    title: str | None
    subtitle: str | None
    life_area_insights: dict[str, str] | None = None
    is_premium_content: bool = False
    # Listing metadata (category chip + avatar emoji) — always present,
    # never gated, deterministic from the reading's own dims
    # (scoring.py::reading_category_and_emoji). Defaults exist only so
    # InnerReadingOut.model_validate(reading) succeeds before
    # reading_content_for_plan()'s merge supplies the real values — see
    # readings.py::_serialize.
    category: str = ""
    emoji: str = ""
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime


class InnerStateSnapshotOut(BaseModel):
    id: UUID
    source_type: str
    check_in_session_id: UUID | None
    inner_reading_id: UUID | None
    emotional_energy: int
    mental_clarity: int
    inner_pressure: int
    grounding: int
    colour_key: str | None
    # The six narrative fields — each stored as one JSONB {"en", "zh"} column
    # on the model (see docs/behaviour_log_0006.md Phase 4), flattened here
    # into _en/_zh pairs to match this app's existing bilingual convention
    # (app/schemas/core_personality.py). Null on snapshots that predate
    # Phase 4, or that came from Inner Reading (still demo/deterministic,
    # no AI outcome generation yet).
    insight_en: str | None
    insight_zh: str | None
    reflection_question_en: str | None
    reflection_question_zh: str | None
    reminder_en: str | None
    reminder_zh: str | None
    current_focus_en: str | None
    current_focus_zh: str | None
    friendly_advice_en: str | None
    friendly_advice_zh: str | None
    affirmation_en: str | None
    affirmation_zh: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, snapshot) -> "InnerStateSnapshotOut":
        def bi(field: str) -> tuple[str | None, str | None]:
            value = getattr(snapshot, field) or {}
            return value.get("en"), value.get("zh")

        insight_en, insight_zh = bi("insight")
        reflection_question_en, reflection_question_zh = bi("reflection_question")
        reminder_en, reminder_zh = bi("reminder")
        current_focus_en, current_focus_zh = bi("current_focus")
        friendly_advice_en, friendly_advice_zh = bi("friendly_advice")
        affirmation_en, affirmation_zh = bi("affirmation")

        return cls(
            id=snapshot.id, source_type=snapshot.source_type,
            check_in_session_id=snapshot.check_in_session_id, inner_reading_id=snapshot.inner_reading_id,
            emotional_energy=snapshot.emotional_energy, mental_clarity=snapshot.mental_clarity,
            inner_pressure=snapshot.inner_pressure, grounding=snapshot.grounding,
            colour_key=snapshot.colour_key,
            insight_en=insight_en, insight_zh=insight_zh,
            reflection_question_en=reflection_question_en, reflection_question_zh=reflection_question_zh,
            reminder_en=reminder_en, reminder_zh=reminder_zh,
            current_focus_en=current_focus_en, current_focus_zh=current_focus_zh,
            friendly_advice_en=friendly_advice_en, friendly_advice_zh=friendly_advice_zh,
            affirmation_en=affirmation_en, affirmation_zh=affirmation_zh,
            created_at=snapshot.created_at,
        )


class CheckInResultsOut(BaseModel):
    session: CheckInSessionOut
    snapshot: InnerStateSnapshotOut | None


class TrendPointOut(BaseModel):
    date: str
    label: str
    emotional_energy: int | None
    mental_clarity: int | None
    inner_pressure: int | None
    grounding: int | None


class TrendOut(BaseModel):
    period: str
    points: list[TrendPointOut]
