from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CalculateRequest(BaseModel):
    date_of_birth: str = Field(description="YYYY-MM-DD")
    language: str = "en"  # "en" | "zh"


class CorePersonalityResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    primary_language: str | None
    generation_status: str  # PARTIAL | READY

    birthday_number: int | None
    birthday_number_content_en: str | None
    birthday_number_content_zh: str | None

    life_path_number: int | None
    life_path_number_content_en: str | None
    life_path_number_content_zh: str | None

    talent_number: str | None
    talent_number_content_en: str | None
    talent_number_content_zh: str | None

    title_en: str | None
    title_zh: str | None
    subtitle_en: str | None
    subtitle_zh: str | None
    overview_en: str | None
    overview_zh: str | None
    summary_en: str | None
    summary_zh: str | None

    scarlet_score: int | None
    russet_score: int | None
    gold_score: int | None
    forest_score: int | None
    ocean_score: int | None

    generated_at: datetime
