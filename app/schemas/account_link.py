from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


# --- Admin CRUD for bangle-bazi-admin's Auren Accounts page (via
# bracelet-management-backend) — see AUREN_ACCOUNTS_ADMIN_CRUD_PLAN.md ---


class AdminCreateUserRequest(BaseModel):
    display_name: str
    phone_number: str = Field(pattern=r"^\d{8,15}$")
    email: EmailStr
    # Admin-typed, stored once at creation — never editable or returned by
    # any endpoint afterward (see plan doc §2). Only the account holder can
    # change it later, through the app's own /me/password.
    password: str = Field(min_length=6)


class AdminUpdateUserRequest(BaseModel):
    display_name: str | None = None
    email: EmailStr | None = None
    plan: Literal["FREE", "PREMIUM"] | None = None
    # Only consulted when plan == "PREMIUM"; defaults to MONTHLY server-side
    # if omitted.
    billing_cycle: Literal["MONTHLY", "YEARLY"] | None = None


class AdminDeleteUserResponse(BaseModel):
    deleted: bool
    # Lets the caller (bracelet-management-backend) know whether it also
    # needs to clean up its own AurenAccountLink row — that one can't
    # cascade, it lives in a different database. See plan doc §4.
    had_linked_bracelet_account: bool
    bracelet_user_id: UUID | None = None
