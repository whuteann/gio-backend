from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RecommendationItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type: str
    reference_id: str | None
    title: str
    reason: str
    rank: int
    image_url: str | None
    price: float | None
    destination_url: str | None


class RecommendationOut(BaseModel):
    id: UUID
    current_focus: str
    summary: str
    colour_key: str
    colour_name: str
    colour_swatch: str
    status: str
    generated_at: datetime
    items: list[RecommendationItemOut]
