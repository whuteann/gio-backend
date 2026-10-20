from pydantic import BaseModel, EmailStr, Field

# Plain digits only — no "+", spaces or dashes. The frontend owns any
# country-code UX; this is just "is it a string of digits" validation.
# Normalization (stripping whitespace) happens at the query site, same
# convention the old email field used (see app/api/v1/endpoints/auth.py).
_PHONE_PATTERN = r"^\d{8,15}$"


class RegisterRequest(BaseModel):
    phone_number: str = Field(pattern=_PHONE_PATTERN)
    password: str
    display_name: str
    language: str = "en"
    # Optional — no longer the login identity, kept only for Xendit
    # checkout/invoicing (see app/models/user.py).
    email: EmailStr | None = None


class LoginRequest(BaseModel):
    phone_number: str = Field(pattern=_PHONE_PATTERN)
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


# --- Forgot-password flow (see PASSWORD_RESET_PLAN.md) ---------------------

_OTP_PATTERN = r"^\d{6}$"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyResetOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=_OTP_PATTERN)


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=_OTP_PATTERN)
    # Same rule as ChangePasswordRequest and the register form, so all three
    # reject exactly the same passwords. The "confirm password" field is a
    # frontend-only check — a second identical value buys the API nothing.
    new_password: str = Field(min_length=6)


class GenericDetailResponse(BaseModel):
    detail: str


class OtpValidResponse(BaseModel):
    valid: bool
