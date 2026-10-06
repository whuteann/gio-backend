import logging
import time
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


def strip_phone_number(phone: str) -> str:
    """Normalize to this backend's own native format: plain digits, no
    "+", spaces or dashes (see app/schemas/auth.py's _PHONE_PATTERN) —
    mirrors braceletBackend's normalize_phone_number, which instead
    normalizes to E.164. Each backend normalizes incoming numbers to its
    own convention; callers never need to know which format to send.
    """
    if not phone:
        return phone
    return str(phone).strip().replace(" ", "").replace("-", "").replace("+", "")


def notify_bracelet_backend_of_signup(user: User) -> None:
    """Fire-and-forget webhook to braceletBackend right after a new Auren
    account commits — keeps its AurenUserMirror current (see
    AUREN_GIO_ACCOUNT_LINKING_PLAN.md §4a). Best-effort: a failure here
    must never block or roll back the signup itself.
    """
    try:
        httpx.post(
            f"{settings.bracelet_backend_url}/internal/auren/sync-user",
            json={
                "auren_user_id": str(user.id),
                "phone_number": user.phone_number,
                "display_name": user.display_name,
                "email": user.email,
            },
            headers={"X-Service-Key": settings.internal_link_secret},
            timeout=5.0,
        )
    except httpx.HTTPError as e:
        logger.warning(f"Auren signup sync to braceletBackend failed for user {user.id}: {e}")


def get_user_by_bracelet_user_id(db: Session, bracelet_user_id: UUID) -> User | None:
    return db.query(User).filter(User.linked_bracelet_user_id == bracelet_user_id).first()


# 3 attempts, short fixed backoff — see AUREN_SIGN_IN_WITH_GIO_PLAN.md §4 for
# why this is retry-then-log rather than blocking signup or a background
# reconciliation sweep (neither is used here, deliberately).
_LINK_FROM_SIGNUP_BACKOFF_SECONDS = (0.5, 1.0)


def link_from_signup(bracelet_user_id: UUID, auren_user_id: UUID, auren_phone_number: str) -> bool:
    """Writes the mirrored AurenAccountLink row on braceletBackend right
    after "Sign in with Gio" provisions a new Auren account. Retries a
    couple of times on failure; if all attempts fail, logs clearly enough
    to grep for later and returns False — the caller must never block the
    signup response on this, the new Auren account is fully usable either
    way. Returns True on success.
    """
    url = f"{settings.bracelet_backend_url}/internal/auren/link-from-signup"
    payload = {
        "bracelet_user_id": str(bracelet_user_id),
        "auren_user_id": str(auren_user_id),
        "auren_phone_number": auren_phone_number,
    }
    headers = {"X-Service-Key": settings.internal_link_secret}

    attempts = len(_LINK_FROM_SIGNUP_BACKOFF_SECONDS) + 1
    for attempt in range(1, attempts + 1):
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=5.0)
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            is_last = attempt == attempts
            logger.warning(
                f"link-from-signup attempt {attempt}/{attempts} failed for "
                f"bracelet_user_id={bracelet_user_id} auren_user_id={auren_user_id}: {e}"
            )
            if is_last:
                logger.error(
                    "link-from-signup exhausted retries — orphaned link: "
                    f"bracelet_user_id={bracelet_user_id} auren_user_id={auren_user_id} "
                    f"phone={auren_phone_number}. Auren account is fully usable; "
                    "braceletBackend's AurenAccountLink row needs manual backfill."
                )
                return False
            time.sleep(_LINK_FROM_SIGNUP_BACKOFF_SECONDS[attempt - 1])
    return False
