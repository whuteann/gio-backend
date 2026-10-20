#!/usr/bin/env python3
"""Send one real test email using the configured MAIL_* settings.

Confirms the whole chain works end to end: settings loaded, SMTP
reachable, login accepted, message delivered. Run it inside the app
container, where the real .env is already loaded:

    docker compose exec app python scripts/send_test_email.py you@example.com

Exits non-zero if MAIL_* isn't configured or the send fails — check the
logged exception for the SMTP server's actual error (auth failure, wrong
port for the TLS mode, etc.).
"""
import argparse
import sys
from pathlib import Path

# `python scripts/send_test_email.py` puts /app/scripts on sys.path, not /app,
# so the `app` package is not importable without this — same shim as
# scripts/create_account.py. Keeps the documented invocation working instead
# of requiring PYTHONPATH=/app or `python -m`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.mail import send_email  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipient", help="Where to send the test email")
    args = parser.parse_args()

    ok = send_email(
        recipients=[args.recipient],
        subject="Auren mail service test",
        html_body="<p>This is a test email from gio-backend's app/services/mail.py.</p>",
    )
    if not ok:
        print("Send failed or mail is not configured — check the logged warning/exception above.", file=sys.stderr)
        return 1
    print(f"Sent — check {args.recipient}'s inbox (and spam folder).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
