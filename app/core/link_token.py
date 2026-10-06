"""Short-lived, purpose-scoped tokens for the Gio<->Auren account-linking
flows (see AUREN_GIO_ACCOUNT_LINKING_PLAN.md at the repo root).

Mirror of braceletBackend's app/core/link_token.py — signed with
INTERNAL_LINK_SECRET, the symmetric secret shared between the two
backends. Distinct from this module's own create_access_token/
create_refresh_token secret: these tokens are never valid as session
tokens because of the `purpose` claim, checked explicitly below.
"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.config import settings

LINK_TOKEN_TTL_MINUTES = 5

# Much shorter than the linking tokens above — an SSO handoff token is
# meant to be consumed within the same browser redirect that minted it,
# not held across a multi-step wizard. Unlike the linking tokens (bounded
# blast radius — they can only link/unlink an account), this one grants a
# full logged-in session, so the window it's valid for matters more.
SSO_TOKEN_TTL_SECONDS = 60

PURPOSE_VERIFY_GIO = "verify-gio"
PURPOSE_VERIFY_AUREN = "verify-auren"
PURPOSE_ADMIN_UNLINK = "admin-unlink"
PURPOSE_SSO_TO_GIO = "sso-to-gio"
PURPOSE_SSO_TO_AUREN = "sso-to-auren"


def issue_link_token(purpose: str, **claims: Any) -> str:
    payload: dict[str, Any] = {
        "purpose": purpose,
        "exp": datetime.utcnow() + timedelta(minutes=LINK_TOKEN_TTL_MINUTES),
        "iat": datetime.utcnow(),
        **claims,
    }
    return jwt.encode(payload, settings.internal_link_secret, algorithm="HS256")


def issue_sso_token(purpose: str, **claims: Any) -> str:
    payload: dict[str, Any] = {
        "purpose": purpose,
        "exp": datetime.utcnow() + timedelta(seconds=SSO_TOKEN_TTL_SECONDS),
        "iat": datetime.utcnow(),
        **claims,
    }
    return jwt.encode(payload, settings.internal_link_secret, algorithm="HS256")


def verify_link_token(token: str, expected_purpose: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.internal_link_secret, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired link token.",
        )

    if payload.get("purpose") != expected_purpose:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Link token is not valid for this operation.",
        )

    return payload
