import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class NarrativeProfile(Base):
    """Pure container/query anchor — see docs/behaviour_log_0005.md. No
    content of its own; every real record lives on NarrativeEntry."""

    __tablename__ = "narrative_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="narrative_profile")
    entries = relationship(
        "NarrativeEntry", back_populates="profile", cascade="all, delete-orphan",
        order_by="NarrativeEntry.created_at.desc()",
    )


class NarrativeEntry(Base):
    """Private memory per reflection or journal; last five ground future output."""

    __tablename__ = "narrative_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    narrative_profile_id = Column(UUID(as_uuid=True), ForeignKey("narrative_profiles.id", ondelete="CASCADE"), nullable=False)
    source_type = Column(String, nullable=False)  # CHECK_IN | INNER_READING | JOURNAL
    check_in_session_id = Column(UUID(as_uuid=True), ForeignKey("check_in_sessions.id", ondelete="CASCADE"), nullable=True)
    inner_reading_id = Column(UUID(as_uuid=True), ForeignKey("inner_readings.id", ondelete="CASCADE"), nullable=True)
    journal_entry_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=True)
    summary = Column(String, nullable=False)  # ~20-word AI summary
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    profile = relationship("NarrativeProfile", back_populates="entries")

    __table_args__ = (
        CheckConstraint(
            "(check_in_session_id IS NOT NULL)::int + (inner_reading_id IS NOT NULL)::int + (journal_entry_id IS NOT NULL)::int = 1",
            name="ck_narrative_entry_single_source",
        ),
        # Serves the "last 5 entries for this profile" query directly —
        # the exact access pattern generation will use.
        Index("ix_narrative_entries_profile_created", "narrative_profile_id", created_at.desc()),
    )
