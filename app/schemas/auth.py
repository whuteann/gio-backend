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
    # Required, not optional: signup now emails a verification code, and an
    # account created without an address could never be verified and so
    # could never log in.
    email: EmailStr


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


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=_OTP_PATTERN)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class RegisterResponse(BaseModel):
    """No tokens. Registration creates the account and emails a code; the
    session is issued by /auth/verify-email once that code checks out."""

    email: EmailStr
    verification_required: bool = True
    detail: str


class LoginUnverifiedResponse(BaseModel):
    """What /auth/login returns for a correct password on an account that
    never verified. A fresh code has already been sent, so the client routes
    to the same verify page a new signup lands on."""

    email: EmailStr
    verification_required: bool = True
    detail: str
