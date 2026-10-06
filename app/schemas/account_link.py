from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CheckPhoneRequest(BaseModel):
    phone_number: str


class CheckPhoneResponse(BaseModel):
    exists: bool


class AuthenticateRequest(BaseModel):
    phone_number: str
    password: str


class AuthenticateResponse(BaseModel):
    verify_auren_token: str
    display_name: str
    plan: str | None = None


class IssueAssertionResponse(BaseModel):
    verify_auren_token: str


class ConfirmRequest(BaseModel):
    verify_gio_token: str
    verify_auren_token: str


class ConfirmResponse(BaseModel):
    linked: bool


class LinkStatusResponse(BaseModel):
    linked: bool
    bracelet_user_id: UUID | None = None


class HandoffResponse(BaseModel):
    sso_token: str


class SsoExchangeRequest(BaseModel):
    sso_token: str


class UnlinkRequest(BaseModel):
    admin_unlink_token: str


class UnlinkResponse(BaseModel):
    unlinked: bool


class AdminUserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    auren_user_id: UUID
    phone_number: str
    display_name: str
    email: str | None
    created_at: datetime
    linked_bracelet_user_id: UUID | None
    last_login_at: datetime | None
    plan: str | None
    subscription_status: str | None
    renews_at: datetime | None
    trial_ends_at: datetime | None
    check_in_count_today: int
    inner_reading_count_today: int


class AdminUserListResponse(BaseModel):
    items: list[AdminUserListItem]
    total: int
    page: int
    page_size: int


class SignInWithGioRequest(BaseModel):
    verify_gio_token: str
    display_name: str
    # Plaintext — used only to seed a brand-new account's password_hash on
    # first "Sign in with Gio" (see AUREN_SIGN_IN_WITH_GIO_PLAN.md §3a).
    # Ignored entirely on the returning-user path.
    password: str


class SignInWithGioResponse(BaseModel):
    is_new: bool
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
