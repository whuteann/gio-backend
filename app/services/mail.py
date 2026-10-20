"""Outbound email — the foundation, not tied to any specific trigger yet.

Plain stdlib smtplib, not a new dependency — the same proven approach as
bracelet-management-backend's app/services/appointment_notifications.py
(`_send_email`), which is the real, actively-used implementation in that
repo (as opposed to that repo's *other*, unused app/services/mail.py,
which wraps fastapi-mail and nothing actually calls). This module is that
pattern generalized into its own reusable function, with one deliberate
difference: best-effort handling lives *inside* send_email() itself
(catch, log, return False) rather than at each call site — matching this
codebase's own house style (app/services/product_api.py,
app/services/lumenart.py, notify_bracelet_backend_of_signup, ...), where a
vendor/infra call never raises into its caller's control flow.

Not yet wired to any feature (no signup/reset-password email exists in
this codebase today) — call send_email() from whatever triggers one.
"""

import logging
import re
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html_summary(html: str) -> str:
    """A plain-text fallback for the HTML body — just enough for mail
    clients that render text/plain, not a real HTML-to-text conversion."""
    text = _TAG_RE.sub("", html)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def send_email(recipients: list[str], subject: str, html_body: str) -> bool:
    """Best-effort — a misconfigured or unreachable mail server must never
    raise into the caller's request/transaction. Returns True on success,
    False otherwise (not configured, no recipients, or the send failed);
    callers that care about delivery should log/alert on False, not treat
    it as an exception to handle."""
    if not recipients:
        logger.warning("send_email called with no recipients for subject %r — skipping.", subject)
        return False
    if not settings.mail_server or not settings.mail_username or not settings.mail_password:
        logger.warning("Mail not configured (MAIL_SERVER/MAIL_USERNAME/MAIL_PASSWORD) — skipping email %r.", subject)
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.mail_from_name} <{settings.mail_from or settings.mail_username}>"
    message["To"] = ", ".join(recipients)
    message.set_content(_strip_html_summary(html_body))
    message.add_alternative(html_body, subtype="html")

    try:
        if settings.mail_port == 465:
            with smtplib.SMTP_SSL(settings.mail_server, settings.mail_port, timeout=settings.mail_timeout_seconds) as server:
                server.login(settings.mail_username, settings.mail_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(settings.mail_server, settings.mail_port, timeout=settings.mail_timeout_seconds) as server:
                if settings.mail_verify_tls:
                    server.starttls()
                server.login(settings.mail_username, settings.mail_password)
                server.send_message(message)
    except (smtplib.SMTPException, OSError):
        logger.exception("Failed to send email %r to %s.", subject, recipients)
        return False

    logger.info("Sent email %r to %s.", subject, recipients)
    return True
