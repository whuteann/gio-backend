"""Forgot-password OTP flow — see PASSWORD_RESET_PLAN.md.

The code itself is the only credential here: there is deliberately no
reset token. With the OTP and the new password submitted from one page,
a token would add a JWT type, a row lookup and its own expiry semantics
while protecting nothing extra — the code is already hashed at rest,
attempt-limited, short-lived and single-use.
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
from app.services.email_templates import PASSWORD_RESET_CODE_TTL_MINUTES, password_reset_code
from app.services.mail import send_email

logger = logging.getLogger(__name__)

CODE_LENGTH = 6
CODE_TTL = timedelta(minutes=PASSWORD_RESET_CODE_TTL_MINUTES)
MAX_ATTEMPTS = 3
# One limit, per account. Enough to stop an inbox being bombed, and it can
# never lock out anyone but the account being targeted — unlike a per-IP
# limit, which behind nginx would be one global bucket (nothing here reads
# X-Forwarded-For). See PASSWORD_RESET_PLAN.md §4.2.
RATE_LIMIT_MAX = 3
RATE_LIMIT_WINDOW = timedelta(minutes=15)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(CODE_LENGTH))


def find_user_by_email(db: Session, email: str) -> User | None:
    normalized = normalize_email(email)
    if not normalized:
        return None
    return db.query(User).filter(User.email == normalized).first()


def _rate_limited(db: Session, user_id: uuid.UUID) -> bool:
    recent = (
        db.query(PasswordResetOtp)
        .filter(
            PasswordResetOtp.user_id == user_id,
            PasswordResetOtp.created_at >= _now() - RATE_LIMIT_WINDOW,
        )
        .count()
    )
    return recent >= RATE_LIMIT_MAX


def _active_code(db: Session, user_id: uuid.UUID) -> PasswordResetOtp | None:
    """The newest code that is still usable: unconsumed, unexpired, and
    under the attempt ceiling."""
    return (
        db.query(PasswordResetOtp)
        .filter(
            PasswordResetOtp.user_id == user_id,
            PasswordResetOtp.consumed_at.is_(None),
            PasswordResetOtp.expires_at > _now(),
            PasswordResetOtp.attempts < PasswordResetOtp.max_attempts,
        )
        .order_by(PasswordResetOtp.created_at.desc())
        .first()
    )


def request_code(db: Session, email: str) -> None:
    """Best-effort and silent by design. The endpoint returns the same
    response whatever happens in here — unknown address, account with no
    email, rate limit hit, or a mail server that is down — so nothing can
    be used to probe whether an account exists.
    """
    user = find_user_by_email(db, email)
    if user is None:
        logger.info("Password reset requested for an address with no account.")
        return
    if _rate_limited(db, user.id):
        logger.warning("Password reset rate limit hit for user=%s.", user.id)
        return

    # Supersede anything outstanding, so only the newest code works.
    for stale in db.query(PasswordResetOtp).filter(
        PasswordResetOtp.user_id == user.id, PasswordResetOtp.consumed_at.is_(None)
    ):
        stale.consumed_at = _now()

    code = _generate_code()
    db.add(
        PasswordResetOtp(
            id=uuid.uuid4(),
            user_id=user.id,
            code_hash=hash_password(code),
            expires_at=_now() + CODE_TTL,
        )
    )
    db.commit()

    subject, html_body = password_reset_code(
        display_name=user.display_name, code=code, language=user.preferred_language
    )
    if not send_email(recipients=[user.email], subject=subject, html_body=html_body):
        # ERROR, not warning: /auth/forgot-password answers 200 regardless,
        # so an unconfigured or unreachable mail server is indistinguishable
        # from success at the UI. This log line is the only signal that the
        # feature is silently dead.
        logger.error("Password reset code generated for user=%s but the email FAILED to send.", user.id)


def verify_code(db: Session, email: str, code: str) -> PasswordResetOtp | None:
    """Returns the matching row, or None. Every failure looks the same to
    the caller — wrong code, expired code, used code, no request at all and
    unknown address are not distinguished, so none of them leak."""
    user = find_user_by_email(db, email)
    if user is None:
        return None

    otp = _active_code(db, user.id)
    if otp is None:
        return None

    # Only *failures* count against the ceiling. Counting every call would
    # mean the happy path spends two attempts — one at /verify-reset-otp and
    # one at /reset-password, which re-checks the code — so a single typo
    # beforehand would exhaust the budget and reject a correct code.
    if not verify_password(code, otp.code_hash):
        otp.attempts += 1
        db.commit()
        logger.info("Password reset code mismatch for user=%s (%s failed attempts).", user.id, otp.attempts)
        return None
    return otp


def reset_password(db: Session, email: str, code: str, new_password: str) -> bool:
    """Verifies the code one last time, then sets the password and consumes
    the code. False means the code was not valid."""
    otp = verify_code(db, email, code)
    if otp is None:
        return False

    user = db.get(User, otp.user_id)
    if user is None:
        return False

    user.password_hash = hash_password(new_password)
    otp.consumed_at = _now()
    db.commit()
    logger.info("Password reset completed for user=%s.", user.id)
    return True
