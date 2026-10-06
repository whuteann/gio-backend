import logging
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
            f"{settings.bracelet_backend_url}/api/v1/internal/auren/sync-user",
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
