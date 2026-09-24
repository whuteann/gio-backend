import uuid

from sqlalchemy import (
    ARRAY,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class XPTransaction(Base):
    __tablename__ = "xp_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    source_action = Column(String, nullable=False)
    source_key = Column(String, nullable=False)  # dedupe key, e.g. "CHECK_IN:2026-09-06"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "source_key", name="uq_xp_transaction_dedupe"),)


class UserQuest(Base):
    __tablename__ = "user_quests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    quest = Column(String, nullable=False)  # LOGIN | CHECK_IN | INNER_READING
    date = Column(Date, nullable=False)
    completed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "quest", "date", name="uq_user_quest_per_day"),)


class UserStreak(Base):
    __tablename__ = "user_streaks"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    current = Column(Integer, nullable=False, default=0)
    best = Column(Integer, nullable=False, default=0)
    last_reflection_date = Column(Date, nullable=True)
    milestones_awarded = Column(ARRAY(Integer), nullable=False, default=list)


class GardenProgress(Base):
    __tablename__ = "garden_progress"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    week_start = Column(Date, nullable=False)
    stage = Column(SmallInteger, nullable=False, default=0)
    actions_this_week = Column(Integer, nullable=False, default=0)


class UserBadge(Base):
    __tablename__ = "user_badges"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    badge_key = Column(String, primary_key=True)
    earned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserReward(Base):
    __tablename__ = "user_rewards"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    reward_key = Column(String, primary_key=True)
    state = Column(String, nullable=False, default="LOCKED")
    unlocked_at = Column(DateTime(timezone=True), nullable=True)
    redeemed_at = Column(DateTime(timezone=True), nullable=True)
