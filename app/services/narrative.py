"""Narrative — system memory, never user-facing. See
docs/behaviour_log_0005.md for the model design and
docs/behaviour_log_0006.md Phase 4 for how it's actually populated.
"""

import uuid

from sqlalchemy.orm import Session

from app.models.narrative import NarrativeEntry, NarrativeProfile
from app.models.user import User

RECENT_ENTRY_LIMIT = 5


def get_or_create_narrative_profile(db: Session, user: User) -> NarrativeProfile:
    if user.narrative_profile is not None:
        return user.narrative_profile
    profile = NarrativeProfile(id=uuid.uuid4(), user_id=user.id)
    user.narrative_profile = profile
    db.add(profile)
    db.flush()
    return profile


def recent_narrative_summaries(db: Session, profile: NarrativeProfile, limit: int = RECENT_ENTRY_LIMIT) -> list[str]:
    entries = (
        db.query(NarrativeEntry)
        .filter_by(narrative_profile_id=profile.id)
        .order_by(NarrativeEntry.created_at.desc())
        .limit(limit)
        .all()
    )
    # oldest-to-newest for the prompt — reads as a timeline, not a reverse list
    return [e.summary for e in reversed(entries)]


def create_narrative_entry(
    db: Session,
    profile: NarrativeProfile,
    *,
    source_type: str,
    summary: str,
    check_in_session_id: uuid.UUID | None = None,
    inner_reading_id: uuid.UUID | None = None,
    journal_entry_id: uuid.UUID | None = None,
) -> NarrativeEntry:
    entry = NarrativeEntry(
        id=uuid.uuid4(),
        narrative_profile_id=profile.id,
        source_type=source_type,
        check_in_session_id=check_in_session_id,
        inner_reading_id=inner_reading_id,
        journal_entry_id=journal_entry_id,
        summary=summary,
    )
    db.add(entry)
    db.flush()
    return entry


def lock_user(db: Session, user: User) -> None:
    """Serialize per-user reflection/journal mutations until the caller commits.

    Async endpoints must run this blocking database operation in a worker thread.
    Refresh loaded counters after waiting for an earlier transaction.
    """
    db.query(User).filter_by(id=user.id).populate_existing().with_for_update().one()


def journal_memory(content: str) -> str:
    """Bounded verbatim excerpt, not an invented mood or AI interpretation."""
    compact = " ".join(content.split())
    excerpt = " ".join(compact.split()[:20])[:160]
    suffix = "…" if len(excerpt) < len(compact) else ""
    return f"Journal excerpt: {excerpt}{suffix}"
