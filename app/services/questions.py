"""Question set generation — get-or-generate-and-cache.

The reuse mechanism: the first request for a given key — a `(date,
increment)` pair, for both check-ins and Inner Readings — generates
content and stores it; every subsequent request for that same key, from
any user, reuses the stored row instead of generating again.

Both check-in (docs/behaviour_log_0006.md Phase 2) and Inner Reading
(docs/behaviour_log_0007.md Phase 2) questions are now real AI generation.
"""

from datetime import date as date_type, timezone

from sqlalchemy.orm import Session

from app.models.reflection import CheckInQuestionSet, InnerReadingQuestionSet
from app.models.user import User
from app.services import ai_questions
from app.services import gamification as gam
from app.services.content import DIMENSION_KEYS


def next_check_in_increment(user: User) -> int:
    """Which check-in-of-the-day this user is about to start — 1 if their
    last check-in wasn't today (UTC), otherwise one past their count so
    far today. Pure calculation, no DB writes: `check_in_count_today` is
    only actually persisted on submit (behaviour_log_0006 Phase 4), not
    just from fetching questions."""
    if user.last_check_in_at is None:
        return 1
    last_check_in_date = user.last_check_in_at.astimezone(timezone.utc).date()
    if last_check_in_date < gam.today_utc():
        return 1
    return user.check_in_count_today + 1


def next_inner_reading_increment(user: User) -> int:
    """Exact mirror of next_check_in_increment, for Inner Reading's own
    last_inner_reading_at/inner_reading_count_today pair
    (docs/behaviour_log_0007.md) — deliberately separate from the weekly
    free/Premium entitlement counter."""
    if user.last_inner_reading_at is None:
        return 1
    last_reading_date = user.last_inner_reading_at.astimezone(timezone.utc).date()
    if last_reading_date < gam.today_utc():
        return 1
    return user.inner_reading_count_today + 1


async def get_or_generate_checkin_question_set(db: Session, on_date: date_type, increment: int) -> CheckInQuestionSet:
    existing = db.query(CheckInQuestionSet).filter_by(date=on_date, increment=increment).first()
    if existing:
        return existing
    generation = await ai_questions.generate_checkin_questions()
    questions = [{"dimension": key, "text": getattr(generation, key)} for key in DIMENSION_KEYS]
    question_set = CheckInQuestionSet(
        date=on_date, increment=increment, blueprint_version="checkin-v1-ai", questions=questions,
    )
    db.add(question_set)
    db.flush()
    return question_set


async def get_or_generate_reading_question_set(db: Session, on_date: date_type, increment: int) -> InnerReadingQuestionSet:
    existing = db.query(InnerReadingQuestionSet).filter_by(date=on_date, increment=increment).first()
    if existing:
        return existing
    generation = await ai_questions.generate_reading_questions()
    questions = [
        {"dimension": key, "text": getattr(generation, f"{key}_{n}")}
        for key in DIMENSION_KEYS
        for n in (1, 2)
    ]
    question_set = InnerReadingQuestionSet(
        date=on_date, increment=increment, blueprint_version="reading-v1-ai", questions=questions,
    )
    db.add(question_set)
    db.flush()
    return question_set
