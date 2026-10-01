import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class CorePersonality(Base):
    """The rarely-changing core of a user's identity — see
    docs/behaviour_log_0002.md. 1:1 with User (not versioned, unlike the
    prior archetype-quiz shape this replaces) since how it gets recalibrated
    is being designed separately."""

    __tablename__ = "core_personalities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Every free-text field is bilingual (see docs/behaviour_log_0003.md) —
    # an _en/_zh pair, not a separate translations table: matches
    # sample-logic.py's own reference pattern (one row, two language blobs,
    # generated together) and avoids a join on every read path, same
    # reasoning already applied to colour_key on InnerStateSnapshot.
    title_en = Column(String, nullable=True)  # e.g. "The Open Horizon"
    title_zh = Column(String, nullable=True)
    subtitle_en = Column(String, nullable=True)
    subtitle_zh = Column(String, nullable=True)
    overview_en = Column(String, nullable=True)
    overview_zh = Column(String, nullable=True)

    # Numbers themselves are language-neutral — only their narrative content
    # is bilingual. Each *_points_{en,zh} column holds a JSON array of
    # {"emoji": str, "text": str} objects (app/schemas/common.py::NumberPoint)
    # — point-form content, not a paragraph string (see docs/behaviour_log
    # for the prompt redesign that replaced the old *_content_{en,zh} text
    # columns these were migrated from).
    birthday_number = Column(Integer, nullable=True)
    birthday_number_points_en = Column(JSONB, nullable=True)
    birthday_number_points_zh = Column(JSONB, nullable=True)

    life_path_number = Column(Integer, nullable=True)
    life_path_number_points_en = Column(JSONB, nullable=True)
    life_path_number_points_zh = Column(JSONB, nullable=True)

    # String, not Integer: a richer numerology implementation formats this
    # "XX/N" (e.g. "38/2"), a compound value an Integer column can't hold.
    # Language-neutral, like the other number fields.
    talent_number = Column(String, nullable=True)
    talent_number_points_en = Column(JSONB, nullable=True)
    talent_number_points_zh = Column(JSONB, nullable=True)

    # One column per app/services/content.py::COLOUR_ORDER key — numeric
    # scores, not text, so no language split needed.
    scarlet_score = Column(SmallInteger, nullable=True)
    russet_score = Column(SmallInteger, nullable=True)
    gold_score = Column(SmallInteger, nullable=True)
    forest_score = Column(SmallInteger, nullable=True)
    ocean_score = Column(SmallInteger, nullable=True)

    # AI-facing grounding context for colour + product recommendation — not
    # user-facing copy (that's title/subtitle/overview/the *_content fields).
    summary_en = Column(String, nullable=True)
    summary_zh = Column(String, nullable=True)

    # Bookkeeping for the sequential dual-language generation flow (see
    # docs/behaviour_log_0004.md): POST /calculate generates and persists
    # `primary_language` synchronously, then generates the other language
    # in the background and flips this to READY.
    primary_language = Column(String, nullable=True)  # "en" | "zh"
    generation_status = Column(String, nullable=False, default="PARTIAL")  # PARTIAL | READY

    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="core_personality")
