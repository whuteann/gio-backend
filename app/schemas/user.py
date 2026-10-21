from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    phone_number: str
    email: str | None
    display_name: str
    gid: str
    status: str
    preferred_language: str
    timezone: str
    birthdate: date | None
    # Derived from email_verified_at so the frontend never interprets a
    # timestamp — see UserOut.from_user below.
    email_verified: bool = True
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
    # Added so accounts created before email was collected at signup can
    # acquire one — without it they can never use the forgot-password flow,
    # which is keyed on email. Omitting the field leaves the address
    # untouched; there is deliberately no way to clear it back to null.
    email: EmailStr | None = None


class ChangePasswordRequest(BaseModel):
    # min_length mirrors the frontend register form's rule (see
    # pages/auth/register.tsx) so both sides reject the same passwords.
    new_password: str = Field(min_length=6)
