"""Plan-gating rules — a Python port of gio-member-app/lib/entitlement.ts.

Enforced server-side here (unlike the original frontend-only mock), since
that's the whole point of moving this logic into a real backend.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.reflection import InnerReading
from app.models.user import Subscription

INNER_READING_WEEKLY_FREE_LIMIT = 3
CHECK_IN_HISTORY_FREE_DAYS = 7


def is_premium_active(sub: Subscription) -> bool:
    now = datetime.now(timezone.utc)
    if sub.trial_ends_at and sub.trial_ends_at > now:
        return True
    if sub.plan != "PREMIUM":
        return False
    if sub.status in ("ACTIVE", "PENDING"):
        return True
    if sub.status == "CANCELLED" and sub.expires_at and sub.expires_at > now:
        return True
    return False


def check_in_history_cutoff(sub: Subscription) -> datetime | None:
    """None = no cutoff (show everything). Otherwise, the earliest
    started_at a free user's check-in history should include."""
    if is_premium_active(sub):
        return None
    return datetime.now(timezone.utc) - timedelta(days=CHECK_IN_HISTORY_FREE_DAYS)


def inner_reading_weekly_count(db: Session, user_id: uuid.UUID) -> int:
    """COMPLETED InnerReading rows in the last 7 days — a rolling window,
    same style as check_in_history_cutoff, not a Mon-Sun calendar week."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    return (
        db.query(InnerReading)
        .filter(InnerReading.user_id == user_id, InnerReading.status == "COMPLETED", InnerReading.created_at >= cutoff)
        .count()
    )
