import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
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
    current_focus = Column(String, nullable=False)
    summary = Column(String, nullable=False)
    # Colours are a backend-constant catalog (see app/services/catalog.py), not
    # a DB table, so this stores the key and the response layer resolves the
    # swatch/name/etc. from that constant.
    colour_key = Column(String, nullable=False)
    status = Column(String, nullable=False, default="READY")
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    items = relationship("RecommendationItem", order_by="RecommendationItem.rank", cascade="all, delete-orphan")

    __table_args__ = (
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
    title = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    rank = Column(SmallInteger, nullable=False)
    image_url = Column(String, nullable=True)
    price = Column(Numeric(10, 2), nullable=True)
    destination_url = Column(String, nullable=True)
