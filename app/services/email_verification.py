"""Signup email verification — the twin of password_reset.py.

A new account starts with `email_verified_at` null and holds no session:
/auth/register issues no tokens. Those come from /auth/verify-email once the
emailed code checks out. Login re-sends a code for any account still
unverified, so nobody is permanently stranded by a lost email.
"""

import logging

from sqlalchemy.orm import Session

from app.models.user import User
from app.services import otp as otp_service
from app.services.email_templates import signup_verification_code
from app.services.mail import send_email

logger = logging.getLogger(__name__)

PURPOSE = otp_service.EMAIL_VERIFY


def send_code(db: Session, user: User) -> None:
    """Issue and email a verification code. Best-effort: a mail failure
    leaves the account unverified and retryable rather than breaking the
    signup that triggered it."""
    if not user.email:
        logger.warning("Verification requested for user=%s with no email address.", user.id)
        return

    code = otp_service.issue_code(db, user, PURPOSE)
    if code is None:
        return  # rate limited; issue_code already logged it

    subject, html_body = signup_verification_code(
        display_name=user.display_name, code=code, language=user.preferred_language
    )
    if not send_email(recipients=[user.email], subject=subject, html_body=html_body):
        logger.error("Verification code generated for user=%s but the email FAILED to send.", user.id)


def verify(db: Session, email: str, code: str) -> User | None:
    """Marks the account verified and consumes the code. Returns the user on
    success, None if the code was not valid. Idempotent in effect: a second
    call with the same code finds it consumed and returns None, but the
    account stays verified."""
    otp = otp_service.verify_code(db, email, code, PURPOSE)
    if otp is None:
        return None

    user = db.get(User, otp.user_id)
    if user is None:
        return None

    if user.email_verified_at is None:
        user.email_verified_at = otp_service.now()
    otp.consumed_at = otp_service.now()
    db.commit()
    logger.info("Email verified for user=%s.", user.id)
    return user
