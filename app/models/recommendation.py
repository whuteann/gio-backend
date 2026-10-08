import uuid

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Numeric, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class RecommendationProfile(Base):
    __tablename__ = "recommendation_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    state_snapshot_id = Column(UUID(as_uuid=True), ForeignKey("inner_state_snapshots.id", ondelete="CASCADE"), nullable=False)
    # Nullable: a user can check in before completing onboarding's Core
    # Personality step.
    core_personality_id = Column(UUID(as_uuid=True), ForeignKey("core_personalities.id"), nullable=True)
    trigger_type = Column(String, nullable=False)  # CHECK_IN | INNER_READING
    trigger_check_in_session_id = Column(UUID(as_uuid=True), ForeignKey("check_in_sessions.id", ondelete="CASCADE"), nullable=True)
    trigger_inner_reading_id = Column(UUID(as_uuid=True), ForeignKey("inner_readings.id", ondelete="CASCADE"), nullable=True)
    # NULL on historical per-reflection profiles; one bundle per UTC day now.
    recommendation_date = Column(Date, nullable=True)
    current_focus_zh = Column(String, nullable=True)
    summary_zh = Column(String, nullable=True)
    current_focus = Column(String, nullable=False)
    summary = Column(String, nullable=False)
    # Colours are a backend-constant catalog (see app/services/catalog.py), not
    # a DB table, so this stores the key and the response layer resolves the
    # swatch/name/etc. from that constant.
    colour_key = Column(String, nullable=False)
    # The deterministic stone-type pick (Crystal | Nephrite | Jade) —
    # app/services/content.py::FOCUS_TO_MATERIAL — used both as the
    # vendor-fetch `type=` filter and as the "Material Affinity" key-info
    # shown on the recommendation detail page.
    material_affinity = Column(String, nullable=True)
    # The one unifying bilingual "letter" tying focus pillar + colour +
    # material + picks together — app/services/ai_recommendation.py.
    # Nullable: pre-dates this column, and best-effort like the rest of the
    # AI half (a vendor/AI failure must not block the reflection submit).
    letter_en = Column(String, nullable=True)
    letter_zh = Column(String, nullable=True)
    status = Column(String, nullable=False, default="READY")
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    items = relationship("RecommendationItem", order_by="RecommendationItem.rank", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "recommendation_date", name="uq_recommendation_user_day"),
        CheckConstraint(
            "(trigger_check_in_session_id IS NOT NULL)::int + (trigger_inner_reading_id IS NOT NULL)::int = 1",
            name="ck_recommendation_single_trigger",
        ),
    )


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recommendation_profile_id = Column(
        UUID(as_uuid=True), ForeignKey("recommendation_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type = Column(String, nullable=False)  # COLOUR | ROUTINE | PRODUCT | ...
    reference_id = Column(String, nullable=True)  # e.g. an external product id
    title_zh = Column(String, nullable=True)
    reason_zh = Column(String, nullable=True)
    currency = Column(String, nullable=False, default="MYR", server_default="MYR")
    title = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    rank = Column(SmallInteger, nullable=False)
    image_url = Column(String, nullable=True)
    price = Column(Numeric(10, 2), nullable=True)
    destination_url = Column(String, nullable=True)
    # PRODUCT items only — the stone/material name as a short display tag
    # (app/services/ai_recommendation.py). Language-neutral (English only),
    # like the other PRODUCT-specific fields here.
    material_tag = Column(String, nullable=True)
    # PRODUCT items only — the deterministic stone type this item was
    # drawn from (Crystal | Nephrite | Jade), set in code from which
    # vendor-fetch pool produced the pick, never AI-authored (see
    # app/services/ai_recommendation.py). Distinct from `material_tag`,
    # which is the AI's specific-stone display name (e.g. "Moss Agate").
    category = Column(String, nullable=True)
    # The vendor's own `specifications` blob, cleaned and already zh/en
    # split — app/services/product_api.py::parse_specifications(). A JSON
    # array of {label_en, label_zh, value_en, value_zh}, e.g. Materials/
    # Certification/Inner Diameter. Null/empty when the vendor gave none.
    specifications = Column(JSONB, nullable=True)
