import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # The login identity — a plain string of digits, no formatting (no "+",
    # spaces or dashes); the frontend is responsible for any country-code UX.
    phone_number = Column(String, unique=True, nullable=False, index=True)
    # No longer the login identity (phone_number is) — kept, now optional,
    # purely for Xendit checkout/invoicing (app/services/subscription_payment.py,
    # app/services/invoice.py both fall back to phone_number when this is null).
    email = Column(String, unique=True, nullable=True, index=True)
    password_hash = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    gid = Column(String, unique=True, nullable=False)
    status = Column(String, nullable=False, default="ACTIVE")
    preferred_language = Column(String, nullable=False, default="en")
    timezone = Column(String, nullable=False, default="UTC")
    # Collected once at onboarding; outlives recalibration (see CorePersonality).
    birthdate = Column(Date, nullable=True)
    onboarding_completed_at = Column(DateTime(timezone=True), nullable=True)
    core_personality_last_recalibrated_at = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    # Drives the daily check-in question-set increment (see
    # docs/behaviour_log_0006.md) — if last_check_in_at isn't today (UTC),
    # the next increment is 1 and check_in_count_today is treated as reset;
    # the reset itself is service-layer logic, these two columns just hold
    # the raw facts.
    last_check_in_at = Column(DateTime(timezone=True), nullable=True)
    check_in_count_today = Column(Integer, nullable=False, default=0)
    # Same mechanism as above, for Inner Reading (docs/behaviour_log_0007.md)
    # — deliberately separate from the weekly free/Premium entitlement
    # counter (entitlement.py::inner_reading_weekly_count), which is
    # unrelated and untouched by this pair.
    last_inner_reading_at = Column(DateTime(timezone=True), nullable=True)
    inner_reading_count_today = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Gio<->Auren account linking (see AUREN_GIO_ACCOUNT_LINKING_PLAN.md).
    # braceletBackend holds the other half of this relationship as
    # auren_account_links.bracelet_user_id/auren_user_id — this column is
    # the Auren-side mirror of the same link, kept in sync by the
    # /account-link/confirm and /account-link/unlink endpoints.
    linked_bracelet_user_id = Column(UUID(as_uuid=True), unique=True, nullable=True)
    linked_at = Column(DateTime(timezone=True), nullable=True)

    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")
    core_personality = relationship("CorePersonality", back_populates="user", uselist=False, cascade="all, delete-orphan")
    narrative_profile = relationship("NarrativeProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan = Column(String, nullable=False, default="FREE")
    status = Column(String, nullable=False, default="ACTIVE")
    starts_at = Column(DateTime(timezone=True), nullable=True)
    renews_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    # Set once, the first time this user starts a trial (opt-in, see
    # POST /subscription/start-trial) — never cleared, so its mere presence
    # (even after the 7 days have lapsed) means "trial already used."
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="subscription")
