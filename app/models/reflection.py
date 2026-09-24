import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


# --- Demo "AI question generation" cache ------------------------------------
# Real generation is deferred; these two tables are the reuse mechanism the
# eventual AI step will populate. For now a request that finds no row for
# today's date (check-ins) / the next reading ordinal (inner readings)
# "generates" static placeholder content and stores it, so every later
# request — from any user — for that same date/ordinal reuses the same row.

class CheckInQuestionSet(Base):
    __tablename__ = "check_in_question_sets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(Date, nullable=False, index=True)
    # Which check-in of the day this set is for (1st, 2nd, ...) — see
    # docs/behaviour_log_0006.md. Shared across users at the same
    # (date, increment), reset by the increment resetting each day, not by
    # this table.
    increment = Column(Integer, nullable=False)
    blueprint_version = Column(String, nullable=False, default="checkin-v1-demo")
    questions = Column(JSONB, nullable=False)  # [{dimension, text}]
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("date", "increment", name="uq_check_in_question_set_date_increment"),)


class InnerReadingQuestionSet(Base):
    __tablename__ = "inner_reading_question_sets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(Date, nullable=False, index=True)
    # Which Inner Reading of the day this set is for (1st, 2nd, ...) — exact
    # mirror of CheckInQuestionSet.increment, see docs/behaviour_log_0007.md.
    # Distinct from InnerReading.ordinal (this user's lifetime reading
    # count), which is unrelated and unaffected by this change.
    increment = Column(Integer, nullable=False)
    blueprint_version = Column(String, nullable=False, default="reading-v1-demo")
    questions = Column(JSONB, nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("date", "increment", name="uq_inner_reading_question_set_date_increment"),)


# --- Check-ins ---------------------------------------------------------------

class CheckInSession(Base):
    __tablename__ = "check_in_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String, nullable=False, default="WEB")
    status = Column(String, nullable=False, default="COMPLETED")
    blueprint_version = Column(String, nullable=False)
    private_note = Column(String, nullable=True)
    summary = Column(String, nullable=True)
    # The NarrativeEntry generated for this check-in (see
    # docs/behaviour_log_0006.md) — SET NULL, not CASCADE, so deleting a
    # narrative entry never takes the check-in it came from down with it.
    narrative_entry_id = Column(UUID(as_uuid=True), ForeignKey("narrative_entries.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    answers = relationship("CheckInAnswer", order_by="CheckInAnswer.order_index", cascade="all, delete-orphan")


class CheckInAnswer(Base):
    __tablename__ = "check_in_answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    check_in_session_id = Column(
        UUID(as_uuid=True), ForeignKey("check_in_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension = Column(String, nullable=False)
    question_text = Column(String, nullable=False)
    answer_value = Column(SmallInteger, nullable=False)
    normalized_value = Column(SmallInteger, nullable=False)
    order_index = Column(SmallInteger, nullable=False)
    answered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# --- Inner Readings ------------------------------------------------------------

class InnerReading(Base):
    __tablename__ = "inner_readings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ordinal = Column(Integer, nullable=False)  # this user's 1st / 2nd / ... reading
    status = Column(String, nullable=False, default="COMPLETED")
    blueprint_version = Column(String, nullable=False)
    emotional_energy = Column(SmallInteger, nullable=True)
    mental_clarity = Column(SmallInteger, nullable=True)
    inner_pressure = Column(SmallInteger, nullable=True)
    grounding = Column(SmallInteger, nullable=True)
    result_summary = Column(String, nullable=True)
    narrative = Column(String, nullable=True)
    insight = Column(String, nullable=True)
    reflection_question = Column(String, nullable=True)
    title = Column(String, nullable=True)
    subtitle = Column(String, nullable=True)
    # AI-generated per reading (docs/behaviour_log_0007.md), replacing the
    # old static content.py::LIFE_AREA_INSIGHTS lookup-by-focus-key.
    # {"work": ..., "relationships": ..., "personal_growth": ...,
    # "conflict_management": ...}. Depth-gating (Premium vs free) still
    # happens at read time (scoring.py::reading_content_for_plan), not here.
    life_area_insights = Column(JSONB, nullable=True)
    narrative_entry_id = Column(UUID(as_uuid=True), ForeignKey("narrative_entries.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    answers = relationship("InnerReadingAnswer", order_by="InnerReadingAnswer.order_index", cascade="all, delete-orphan")


class InnerReadingAnswer(Base):
    __tablename__ = "inner_reading_answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inner_reading_id = Column(
        UUID(as_uuid=True), ForeignKey("inner_readings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension = Column(String, nullable=False)
    question_text = Column(String, nullable=False)
    answer_value = Column(SmallInteger, nullable=False)
    normalized_value = Column(SmallInteger, nullable=False)
    order_index = Column(SmallInteger, nullable=False)
    answered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# --- Inner state snapshots ----------------------------------------------------
# Produced by either a check-in or an inner reading — exactly one of the two
# FKs below is set (see the CheckConstraint), never both/neither.

class InnerStateSnapshot(Base):
    __tablename__ = "inner_state_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String, nullable=False)  # CHECK_IN | INNER_READING
    check_in_session_id = Column(UUID(as_uuid=True), ForeignKey("check_in_sessions.id", ondelete="CASCADE"), nullable=True)
    inner_reading_id = Column(UUID(as_uuid=True), ForeignKey("inner_readings.id", ondelete="CASCADE"), nullable=True)
    # The 4 pillars — see docs/behaviour_log_0002.md.
    emotional_energy = Column(SmallInteger, nullable=False)
    mental_clarity = Column(SmallInteger, nullable=False)
    inner_pressure = Column(SmallInteger, nullable=False)
    grounding = Column(SmallInteger, nullable=False)

    colour_key = Column(String, nullable=True)  # current Colour Recommendation, denormalized — a lookup key, not text

    # The six narrative fields — bilingual, one JSONB column per field
    # (e.g. {"en": "...", "zh": "..."}) rather than an _en/_zh String pair,
    # per docs/behaviour_log_0006.md. Generated per check-in/reading from
    # the AI outcome step (Phase 4), grounded on the user's recent
    # NarrativeEntry history.
    insight = Column(JSONB, nullable=True)
    reflection_question = Column(JSONB, nullable=True)
    reminder = Column(JSONB, nullable=True)  # "Reminder for you"
    current_focus = Column(JSONB, nullable=True)  # ongoing journey, e.g. "Finding Clarity"
    friendly_advice = Column(JSONB, nullable=True)
    affirmation = Column(JSONB, nullable=True)
    # AI-facing grounding context for colour + product recommendation — not
    # user-facing copy (that's insight/reflection_question/reminder/etc.).
    # Not part of the six fields above, stays a plain bilingual String pair.
    summary_en = Column(String, nullable=True)
    summary_zh = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        CheckConstraint(
            "(check_in_session_id IS NOT NULL)::int + (inner_reading_id IS NOT NULL)::int = 1",
            name="ck_inner_state_snapshot_single_source",
        ),
    )
