"""Emailed one-time codes — the generic machinery, shared by every flow.

Grew out of the forgot-password flow (PASSWORD_RESET_PLAN.md) and is now
used by signup email verification too. Everything here is keyed on
`(user_id, purpose)`:

**Filtering on `purpose` is not optional.** The column existed from the
start but nothing queried it, so a signup code and a reset code for the
same user shared one pool — requesting either silently consumed the other,
and verification validated against whichever happened to be newest. Every
query below carries the purpose through.

The code itself is the only credential: hashed at rest, attempt-limited,
short-lived and single-use. There is deliberately no token exchange.
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.password_reset import PasswordResetOtp
from app.models.user import User
from app.services.auth import normalize_email

logger = logging.getLogger(__name__)

# Purposes. The column is String(20) — keep these short.
PASSWORD_RESET = "password_reset"
EMAIL_VERIFY = "email_verify"

CODE_LENGTH = 6
CODE_TTL_MINUTES = 10
CODE_TTL = timedelta(minutes=CODE_TTL_MINUTES)
MAX_ATTEMPTS = 3
# One limit, per account per purpose. Enough to stop an inbox being bombed,
# and it can never lock out anyone but the account being targeted — unlike a
# per-IP limit, which behind nginx would be one global bucket.
RATE_LIMIT_MAX = 3
RATE_LIMIT_WINDOW = timedelta(minutes=15)


def now() -> datetime:
    return datetime.now(timezone.utc)


def generate_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(CODE_LENGTH))


def find_user_by_email(db: Session, email: str) -> User | None:
    normalized = normalize_email(email)
    if not normalized:
        return None
    return db.query(User).filter(User.email == normalized).first()


def rate_limited(db: Session, user_id: uuid.UUID, purpose: str) -> bool:
    recent = (
        db.query(PasswordResetOtp)
        .filter(
            PasswordResetOtp.user_id == user_id,
            PasswordResetOtp.purpose == purpose,
            PasswordResetOtp.created_at >= now() - RATE_LIMIT_WINDOW,
        )
        .count()
    )
    return recent >= RATE_LIMIT_MAX


def active_code(db: Session, user_id: uuid.UUID, purpose: str) -> PasswordResetOtp | None:
    """The newest code for this purpose that is still usable: unconsumed,
    unexpired, and under the attempt ceiling."""
    return (
        db.query(PasswordResetOtp)
        .filter(
            PasswordResetOtp.user_id == user_id,
            PasswordResetOtp.purpose == purpose,
            PasswordResetOtp.consumed_at.is_(None),
            PasswordResetOtp.expires_at > now(),
            PasswordResetOtp.attempts < PasswordResetOtp.max_attempts,
        )
        .order_by(PasswordResetOtp.created_at.desc())
        .first()
    )


def issue_code(db: Session, user: User, purpose: str) -> str | None:
    """Supersede this purpose's outstanding codes and store a fresh one.

    Returns the plaintext code for the caller to email, or None when the
    rate limit was hit. Commits — the code must survive even if the mail
    send that follows fails.
    """
    if rate_limited(db, user.id, purpose):
        logger.warning("OTP rate limit hit for user=%s purpose=%s.", user.id, purpose)
        return None

    # Only this purpose's codes are superseded; a live password-reset code
    # must survive a signup-verification request and vice versa.
    for stale in db.query(PasswordResetOtp).filter(
        PasswordResetOtp.user_id == user.id,
        PasswordResetOtp.purpose == purpose,
        PasswordResetOtp.consumed_at.is_(None),
    ):
        stale.consumed_at = now()

    code = generate_code()
    db.add(
        PasswordResetOtp(
            id=uuid.uuid4(),
            user_id=user.id,
            purpose=purpose,
            code_hash=hash_password(code),
            expires_at=now() + CODE_TTL,
        )
    )
    db.commit()
    return code


def verify_code(db: Session, email: str, code: str, purpose: str) -> PasswordResetOtp | None:
    """Returns the matching row, or None. Every failure looks the same to
    the caller — wrong code, expired code, used code, no request at all and
    unknown address are not distinguished, so none of them leak."""
    user = find_user_by_email(db, email)
    if user is None:
        return None

    otp = active_code(db, user.id, purpose)
    if otp is None:
        return None

    # Only *failures* count against the ceiling. Counting every call would
    # mean a happy path that verifies twice spends two attempts, so a single
    # typo beforehand would exhaust the budget and reject a correct code.
    if not verify_password(code, otp.code_hash):
        otp.attempts += 1
        db.commit()
        logger.info("OTP mismatch for user=%s purpose=%s (%s failed attempts).", user.id, purpose, otp.attempts)
        return None
    return otp
