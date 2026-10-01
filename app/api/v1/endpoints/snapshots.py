from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.reflection import InnerStateSnapshot
from app.models.user import User
from app.schemas.reflection import InnerStateSnapshotOut, TrendOut, TrendPointOut
from app.services.entitlement import is_premium_active
from app.services.gamification import today_utc
from app.services.trend import build_trend_range, build_trend_series

router = APIRouter(prefix="/state-snapshots", tags=["state-snapshots"])


@router.get("/latest", response_model=InnerStateSnapshotOut)
def get_latest_snapshot(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Two most recent rows in one query — the second is "previous", used to
    # compute the dashboard's per-pillar delta (see InnerStateSnapshotOut).
    # Mixes sources deliberately: a check-in and an Inner Reading share the
    # same 4 pillars, so "since you last checked in on yourself" is the
    # intended comparison regardless of which one it was.
    recent = (
        db.query(InnerStateSnapshot)
        .filter_by(user_id=user.id)
        .order_by(InnerStateSnapshot.created_at.desc())
        .limit(2)
        .all()
    )
    if not recent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No check-in or Inner Reading yet.")
    snapshot = recent[0]
    previous = recent[1] if len(recent) > 1 else None
    return InnerStateSnapshotOut.from_model(snapshot, previous=previous)


@router.get("/trend", response_model=TrendOut)
def get_trend(period: str = Query("weekly", pattern="^(weekly|monthly)$"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if period == "monthly" and not is_premium_active(user.subscription):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Monthly trend requires Premium.")

    today = today_utc()
    points = build_trend_range(period, today)
    snapshots = db.query(InnerStateSnapshot).filter_by(user_id=user.id).all()
    series = build_trend_series(points, snapshots, today)

    return TrendOut(
        period=period,
        points=[
            TrendPointOut(
                date=p["date"].isoformat(), label=p["label"],
                emotional_energy=series["emotional_energy"][i], mental_clarity=series["mental_clarity"][i],
                inner_pressure=series["inner_pressure"][i], grounding=series["grounding"][i],
            )
            for i, p in enumerate(points)
        ],
    )
