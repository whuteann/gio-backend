from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SpecificationOut(BaseModel):
    label_en: str
    label_zh: str
    value_en: str
    value_zh: str


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
    category: str | None
    specifications: list[SpecificationOut] | None


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
    # The deterministic stone-type pick (Crystal | Nephrite | Jade) —
    # app/services/content.py::FOCUS_TO_MATERIAL. Null on profiles
    # generated before this column existed.
    material_affinity: str | None
    # The one unifying bilingual letter the AI half writes — null on
    # profiles generated before this existed, or where the AI/vendor step
    # failed (best-effort, same as items being empty).
    letter_en: str | None
    letter_zh: str | None
    status: str
    generated_at: datetime
    items: list[RecommendationItemOut]
