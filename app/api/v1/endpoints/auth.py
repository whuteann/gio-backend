from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, decode_refresh_token, verify_password
from app.dependencies import get_db
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginUnverifiedResponse,
    RegisterResponse,
    ResendVerificationRequest,
    VerifyEmailRequest,
    GenericDetailResponse,
    LoginRequest,
    OtpValidResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyResetOtpRequest,
)
from app.services.account_link import notify_bracelet_backend_of_signup
from app.services import email_verification, otp as otp_service, password_reset
from app.services.recommendation import warm_recommendation
from app.services.auth import create_user, email_taken, normalize_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Creates the account and emails a verification code. Deliberately
    issues NO session: tokens come from /auth/verify-email. An unverified
    account therefore cannot call anything, rather than holding a valid JWT
    while the gate is enforced only in the UI."""
    existing = db.query(User).filter(User.phone_number == payload.phone_number.strip()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this phone number already exists.")
    # `users.email` is UNIQUE but nothing used to check it here, so a
    # duplicate address reached the insert and surfaced as a 500 rather than
    # a 409 (harmless while no client sent an email; not once the register
    # form collects one). Accepted trade-off: this makes signup an
    # email-enumeration oracle, which is the conventional compromise versus
    # silently accepting a duplicate.
    email = normalize_email(payload.email)
    if email and email_taken(db, email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email address already exists.")
    user = create_user(
        db, phone_number=payload.phone_number, password=payload.password,
        display_name=payload.display_name, language=payload.language, email=email,
    )
    db.commit()
    notify_bracelet_backend_of_signup(user)
    email_verification.send_code(db, user)
    return RegisterResponse(email=user.email, detail=_GENERIC_CODE_SENT)


@router.post("/login", response_model=TokenResponse | LoginUnverifiedResponse)
def login(payload: LoginRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone_number == payload.phone_number.strip()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid phone number or password.")
    # An account that never verified gets a fresh code instead of a session,
    # so a lost signup email is recoverable by simply logging in. Checked
    # after the password, so this leaks nothing to someone guessing.
    if user.email_verified_at is None:
        email_verification.send_code(db, user)
        return LoginUnverifiedResponse(email=user.email, detail=_GENERIC_CODE_SENT)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    # Warm today's recommendation so Colour Psychology is instant when they
    # get there. Generation reaches a vendor API and an AI call, so doing it
    # on page load alone would cost the user ~20s on a cold cache.
    background_tasks.add_task(warm_recommendation, user.id)
    return TokenResponse(access_token=create_access_token(str(user.id)), refresh_token=create_refresh_token(str(user.id)))


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user_id = decode_refresh_token(payload.refresh_token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    user = db.get(User, UUID(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    # Warmed here too, not just at login: the session is persisted in the
    # browser, so a daily user can go a month without hitting /auth/login
    # while the recommendation cache turns over every day. Refresh is the
    # path a returning user actually takes.
    background_tasks.add_task(warm_recommendation, user.id)
    # Rotated on every use — a fresh pair each time shrinks the window a
    # leaked refresh token stays useful for, without needing a DB-backed
    # revocation table (see docs/dev_log_0004.md for the trade-off).
    return TokenResponse(access_token=create_access_token(str(user.id)), refresh_token=create_refresh_token(str(user.id)))


# --- Forgot-password flow (see PASSWORD_RESET_PLAN.md) --------------------
#
# All three are unauthenticated. The code emailed to the user is the only
# credential in the flow — there is no reset token, deliberately (§4.3).

# One message for every outcome of /forgot-password. Anything that varied by
# whether the account existed would turn this endpoint into an oracle and
# make the OTP page's copy a lie.
_GENERIC_SENT = "If an account exists for that address, a code has been sent."
_GENERIC_BAD_CODE = "Invalid or expired code."


@router.post("/forgot-password", response_model=GenericDetailResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Always 200 with the same body: unknown address, account without an
    email, rate-limited account and a failed send are indistinguishable from
    success. Everything that could differ is logged server-side instead."""
    password_reset.request_code(db, payload.email)
    return GenericDetailResponse(detail=_GENERIC_SENT)


@router.post("/verify-reset-otp", response_model=OtpValidResponse)
def verify_reset_otp(payload: VerifyResetOtpRequest, db: Session = Depends(get_db)):
    """Exists so the UI only reveals the password fields once the code is
    known good — otherwise someone types a new password twice and *then*
    learns the code was wrong. Does not consume the code; /reset-password
    re-checks it."""
    if password_reset.verify_code(db, payload.email, payload.otp) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_GENERIC_BAD_CODE)
    return OtpValidResponse(valid=True)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Re-verifies the code rather than trusting that /verify-reset-otp was
    called — a client can skip it. Consumes the code on success, so it works
    exactly once."""
    if not password_reset.reset_password(db, payload.email, payload.otp, payload.new_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_GENERIC_BAD_CODE)


# --- Signup email verification -------------------------------------------

_GENERIC_CODE_SENT = "A verification code has been sent to your email."


@router.post("/verify-email", response_model=TokenResponse)
def verify_email(payload: VerifyEmailRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Exchanges a valid code for the account's first session. This is the
    only place a newly registered user gets tokens."""
    user = email_verification.verify(db, payload.email, payload.otp)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_GENERIC_BAD_CODE)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    background_tasks.add_task(warm_recommendation, user.id)
    return TokenResponse(access_token=create_access_token(str(user.id)), refresh_token=create_refresh_token(str(user.id)))


@router.post("/resend-verification", response_model=GenericDetailResponse)
def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    """Always 200 with the same body — unknown address, already-verified
    account and rate-limited account are indistinguishable, same reasoning
    as /auth/forgot-password."""
    user = otp_service.find_user_by_email(db, payload.email)
    if user is not None and user.email_verified_at is None:
        email_verification.send_code(db, user)
    return GenericDetailResponse(detail=_GENERIC_CODE_SENT)
