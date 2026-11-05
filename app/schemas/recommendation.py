from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SpecificationOut(BaseModel):
    """Product specs as the vendor publishes them — services/product_api.py
    splits one bilingual vendor string into these two. No Malay here on
    purpose: there is no Malay in the vendor feed to split, and inventing it
    would mean guessing at material/dimension claims about a real product.
    A Malay reader falls back to English for this block only (see
    gio-member-app's localizedSpec)."""

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
    title_ms: str | None = None
    reason: str
    reason_zh: str | None
    reason_ms: str | None = None
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
    current_focus_ms: str | None = None
    summary: str
    summary_zh: str | None
    summary_ms: str | None = None
    colour_key: str
    colour_name: str
    colour_name_zh: str
    colour_name_ms: str = ""
    colour_swatch: str
    # The deterministic stone-type pick (Crystal | Nephrite | Jade) —
    # app/services/content.py::FOCUS_TO_MATERIAL. Null on profiles
    # generated before this column existed.
    material_affinity: str | None
    # The one unifying letter the AI half writes, one field per language —
    # null on profiles generated before this existed, or where the AI/vendor
    # step failed (best-effort, same as items being empty).
    letter_en: str | None
    letter_zh: str | None
    letter_ms: str | None = None
    status: str
    generated_at: datetime
    items: list[RecommendationItemOut]
