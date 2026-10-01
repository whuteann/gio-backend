from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RecommendationItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type: str
    reference_id: str | None
    title: str
    title_zh: str | None
    reason: str
    reason_zh: str | None
    rank: int
    image_url: str | None
    price: float | None
    currency: str
    destination_url: str | None
    material_tag: str | None


class RecommendationOut(BaseModel):
    id: UUID
    current_focus: str
    current_focus_zh: str | None
    summary: str
    summary_zh: str | None
    colour_key: str
    colour_name: str
    colour_name_zh: str
    colour_swatch: str
    status: str
    generated_at: datetime
    items: list[RecommendationItemOut]
