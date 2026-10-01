"""XP / streak / garden / badges / rewards — a Python port of
gio-member-app/lib/gamification.ts, adapted to mutate real rows instead of
returning new immutable objects.

Simplification: "today" is computed in UTC, not the user's own timezone
(User.timezone exists but isn't applied yet) — fine for a first pass, worth
revisiting before this matters for users near a day boundary.
"""

from datetime import date as date_type, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.gamification import (
    GardenProgress,
    UserBadge,
    UserQuest,
    UserReward,
    UserStreak,
    UserUnlockedContent,
    XPTransaction,
)
from app.services.content import AFFIRMATIONS, INSIGHTS, REFLECTION_QUESTIONS, REWARD_DEFINITIONS

STREAK_MILESTONE_XP = {7: 50, 30: 150, 100: 500}


def today_utc() -> date_type:
    return datetime.now(timezone.utc).date()


def week_start(d: date_type) -> date_type:
    return d - timedelta(days=d.weekday())


def award_xp(db: Session, user_id, amount: int, source_action: str, source_key: str) -> int:
    """Returns the XP actually awarded (0 if `source_key` was already used)."""
    existing = db.query(XPTransaction).filter_by(user_id=user_id, source_key=source_key).first()
    if existing:
        return 0
    db.add(XPTransaction(user_id=user_id, amount=amount, source_action=source_action, source_key=source_key))
    return amount


def total_xp(db: Session, user_id) -> int:
    return db.query(func.coalesce(func.sum(XPTransaction.amount), 0)).filter(XPTransaction.user_id == user_id).scalar()


def complete_quest(db: Session, user_id, quest: str, on_date: date_type) -> bool:
    existing = db.query(UserQuest).filter_by(user_id=user_id, quest=quest, date=on_date).first()
    if existing:
        return False
    db.add(UserQuest(user_id=user_id, quest=quest, date=on_date, completed_at=datetime.now(timezone.utc)))
    return True


def quests_today(db: Session, user_id, on_date: date_type) -> list[str]:
    return [r[0] for r in db.query(UserQuest.quest).filter_by(user_id=user_id, date=on_date).all()]


def all_three_quests_complete(db: Session, user_id, on_date: date_type) -> bool:
    return {"LOGIN", "CHECK_IN", "INNER_READING"}.issubset(set(quests_today(db, user_id, on_date)))


def get_or_create_streak(db: Session, user_id) -> UserStreak:
    streak = db.get(UserStreak, user_id)
    if not streak:
        streak = UserStreak(user_id=user_id, current=0, best=0, last_reflection_date=None, milestones_awarded=[])
        db.add(streak)
        db.flush()
    return streak


def update_streak_for_reflection(db: Session, user_id, on_date: date_type) -> int | None:
    """Advances the streak for a reflection on `on_date`. Returns a newly hit
    milestone (7/30/100), or None."""
    streak = get_or_create_streak(db, user_id)
    if streak.last_reflection_date == on_date:
        return None
    yesterday = on_date - timedelta(days=1)
    streak.current = streak.current + 1 if streak.last_reflection_date == yesterday else 1
    streak.best = max(streak.best, streak.current)
    streak.last_reflection_date = on_date

    milestones = list(streak.milestones_awarded or [])
    new_milestone = None
    if streak.current in STREAK_MILESTONE_XP and streak.current not in milestones:
        milestones.append(streak.current)
        streak.milestones_awarded = milestones
        new_milestone = streak.current
    return new_milestone


def get_or_create_garden(db: Session, user_id) -> GardenProgress:
    garden = db.get(GardenProgress, user_id)
    if not garden:
        garden = GardenProgress(user_id=user_id, week_start=week_start(today_utc()), stage=0, actions_this_week=0)
        db.add(garden)
        db.flush()
    return garden


def refresh_garden_week(garden: GardenProgress, on_date: date_type) -> None:
    current_week = week_start(on_date)
    if garden.week_start != current_week:
        garden.week_start = current_week
        garden.stage = 0
        garden.actions_this_week = 0


def update_garden_for_reflection(db: Session, user_id, on_date: date_type) -> GardenProgress:
    garden = get_or_create_garden(db, user_id)
    refresh_garden_week(garden, on_date)
    garden.actions_this_week += 1
    garden.stage = min(4, garden.actions_this_week)
    return garden


def evaluate_badges(db: Session, user_id, *, streak_best: int, readings_count: int, garden_stage: int, total_xp_amount: int) -> list[str]:
    earned = {r[0] for r in db.query(UserBadge.badge_key).filter_by(user_id=user_id).all()}
    newly_earned: list[str] = []

    def award(key: str) -> None:
        if key not in earned:
            db.add(UserBadge(user_id=user_id, badge_key=key, earned_at=datetime.now(timezone.utc)))
            newly_earned.append(key)

    if streak_best >= 3:
        award("three_day_streak")
    if streak_best >= 14:
        award("two_week_rhythm")
    if readings_count >= 1:
        award("first_insight")
    if readings_count >= 5:
        award("deep_diver")
    if garden_stage >= 4:
        award("first_bloom")
    if total_xp_amount >= 300:
        award("momentum")
    return newly_earned


def evaluate_rewards(db: Session, user_id, *, xp: int, streak_best: int, badge_keys: list[str]) -> None:
    ctx = {"xp": xp, "streak_best": streak_best, "badges": badge_keys}
    existing_keys = {r.reward_key for r in db.query(UserReward).filter_by(user_id=user_id).all()}
    for reward_def in REWARD_DEFINITIONS:
        key = reward_def["key"]
        if key in existing_keys:
            continue
        if reward_def["is_eligible"](ctx):
            db.add(UserReward(user_id=user_id, reward_key=key, state="UNLOCKED", unlocked_at=datetime.now(timezone.utc)))


_UNLOCK_CATALOGS = {
    "AFFIRMATION": AFFIRMATIONS,
    "INSIGHT": INSIGHTS,
    "REFLECTION_QUESTION": REFLECTION_QUESTIONS,
}


def record_content_unlock(db: Session, user_id, category: str, item_id: str) -> bool:
    """Insert-if-not-exists — same append-only, never-revoked shape as
    evaluate_badges. See docs/behaviour_log_0011.md."""
    existing = db.query(UserUnlockedContent).filter_by(user_id=user_id, category=category, item_id=item_id).first()
    if existing:
        return False
    db.add(UserUnlockedContent(user_id=user_id, category=category, item_id=item_id))
    return True


def get_unlocked_content(db: Session, user_id) -> dict[str, list[dict]]:
    """The full 60-item catalog across all 3 categories, each item flagged
    unlocked/locked. A locked item's text is deliberately withheld here,
    not just hidden client-side — the frontend renders it as a black,
    empty badge with no way to learn what it says before earning it."""
    unlocked = {
        (r.category, r.item_id): r.unlocked_at
        for r in db.query(UserUnlockedContent).filter_by(user_id=user_id).all()
    }

    def build(category: str) -> list[dict]:
        items = []
        for item_id, text in _UNLOCK_CATALOGS[category].items():
            unlocked_at = unlocked.get((category, item_id))
            if unlocked_at is not None:
                items.append({
                    "item_id": item_id, "unlocked": True,
                    "text_en": text["en"], "text_zh": text["zh"], "unlocked_at": unlocked_at,
                })
            else:
                items.append({"item_id": item_id, "unlocked": False, "text_en": None, "text_zh": None, "unlocked_at": None})
        return items

    return {
        "affirmations": build("AFFIRMATION"),
        "insights": build("INSIGHT"),
        "reflection_questions": build("REFLECTION_QUESTION"),
    }
