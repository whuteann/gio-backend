from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import NumberPoint


class CalculateRequest(BaseModel):
    date_of_birth: str = Field(description="YYYY-MM-DD")
    language: str = "en"  # services/languages.SUPPORTED


class CorePersonalityResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    primary_language: str | None
    generation_status: str  # PARTIAL (not every language in yet) | READY
    # Which languages are actually present — see languages.record_ready.
    languages_ready: list[str] | None = None

    birthday_number: int | None
    birthday_number_points_en: list[NumberPoint] | None
    birthday_number_points_zh: list[NumberPoint] | None
    birthday_number_points_ms: list[NumberPoint] | None = None

    life_path_number: int | None
    life_path_number_points_en: list[NumberPoint] | None
    life_path_number_points_zh: list[NumberPoint] | None
    life_path_number_points_ms: list[NumberPoint] | None = None

    talent_number: str | None
    talent_number_points_en: list[NumberPoint] | None
    talent_number_points_zh: list[NumberPoint] | None
    talent_number_points_ms: list[NumberPoint] | None = None

    title_en: str | None
    title_zh: str | None
    title_ms: str | None = None
    subtitle_en: str | None
    subtitle_zh: str | None
    subtitle_ms: str | None = None
    overview_en: str | None
    overview_zh: str | None
    overview_ms: str | None = None
    summary_en: str | None
    summary_zh: str | None
    summary_ms: str | None = None

    scarlet_score: int | None
    russet_score: int | None
    gold_score: int | None
    forest_score: int | None
    ocean_score: int | None

    generated_at: datetime
