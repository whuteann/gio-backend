"""Forgot-password flow — see PASSWORD_RESET_PLAN.md.

The OTP machinery itself lives in services/otp.py, shared with signup email
verification. What stays here is the part specific to resetting a password:
the enumeration-safe request, and the state change at the end.
"""

import logging

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.password_reset import PasswordResetOtp
from app.models.user import User
from app.services import otp as otp_service
from app.services.email_templates import password_reset_code
from app.services.mail import send_email

logger = logging.getLogger(__name__)

PURPOSE = otp_service.PASSWORD_RESET


def request_code(db: Session, email: str) -> None:
    """Best-effort and silent by design. The endpoint returns the same
    response whatever happens in here — unknown address, account with no
    email, rate limit hit, or a mail server that is down — so nothing can
    be used to probe whether an account exists.
    """
    user = otp_service.find_user_by_email(db, email)
    if user is None:
        logger.info("Password reset requested for an address with no account.")
        return

    code = otp_service.issue_code(db, user, PURPOSE)
    if code is None:
        return  # rate limited; issue_code already logged it

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
    return otp_service.verify_code(db, email, code, PURPOSE)


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
    otp.consumed_at = otp_service.now()
    db.commit()
    logger.info("Password reset completed for user=%s.", user.id)
    return True
