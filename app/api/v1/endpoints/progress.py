from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.gamification import UserBadge
from app.models.user import User
from app.schemas.gamification import BadgeOut, GardenOut, ProgressOut, StreakOut
from app.services import gamification as gam
from app.services.content import BADGE_DEFINITIONS

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=ProgressOut)
def get_progress(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = gam.today_utc()
    streak = gam.get_or_create_streak(db, user.id)
    garden = gam.get_or_create_garden(db, user.id)
    gam.refresh_garden_week(garden, today)
    quests = gam.quests_today(db, user.id, today)
    xp_total = gam.total_xp(db, user.id)

    earned = {r.badge_key: r.earned_at for r in db.query(UserBadge).filter_by(user_id=user.id).all()}
    badges = [
        BadgeOut(
            key=b["key"], group=b["group"], title=b["title"], description=b["description"], icon=b["icon"],
            earned=b["key"] in earned, earned_at=earned[b["key"]].isoformat() if b["key"] in earned else None,
        )
        for b in BADGE_DEFINITIONS
    ]

    db.commit()

    return ProgressOut(
        xp_total=xp_total,
        streak=StreakOut(
            current=streak.current, best=streak.best,
            last_reflection_date=streak.last_reflection_date.isoformat() if streak.last_reflection_date else None,
            milestones_awarded=list(streak.milestones_awarded or []),
        ),
        garden=GardenOut(week_start=garden.week_start.isoformat(), stage=garden.stage, actions_this_week=garden.actions_this_week),
        quests_today=quests,
        badges=badges,
    )
