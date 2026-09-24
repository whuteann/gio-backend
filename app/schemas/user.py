from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan: str
    status: str
    starts_at: datetime | None
    renews_at: datetime | None
    expires_at: datetime | None
    cancelled_at: datetime | None
    trial_ends_at: datetime | None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    gid: str
    status: str
    preferred_language: str
    timezone: str
    birthdate: date | None
    onboarding_completed_at: datetime | None
    core_personality_last_recalibrated_at: datetime | None
    last_login_at: datetime | None
    created_at: datetime


class MeOut(BaseModel):
    user: UserOut
    subscription: SubscriptionOut


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    preferred_language: str | None = None
    timezone: str | None = None


class ChangePasswordRequest(BaseModel):
    # min_length mirrors the frontend register form's rule (see
    # pages/auth/register.tsx) so both sides reject the same passwords.
    new_password: str = Field(min_length=6)
