from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.gamification import UserReward
from app.models.user import User
from app.schemas.gamification import RewardOut
from app.services.content import REWARD_DEFINITIONS

router = APIRouter(prefix="/rewards", tags=["rewards"])


@router.get("", response_model=list[RewardOut])
def list_rewards(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    states = {r.reward_key: r for r in db.query(UserReward).filter_by(user_id=user.id).all()}
    result = []
    for r in REWARD_DEFINITIONS:
        state = states.get(r["key"])
        result.append(RewardOut(
            key=r["key"], title=r["title"], description=r["description"], icon=r["icon"], requirement=r["requirement"],
            state=state.state if state else "LOCKED",
            unlocked_at=state.unlocked_at.isoformat() if state and state.unlocked_at else None,
            redeemed_at=state.redeemed_at.isoformat() if state and state.redeemed_at else None,
        ))
    return result


@router.post("/{key}/redeem", response_model=RewardOut)
def redeem_reward(key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    definition = next((r for r in REWARD_DEFINITIONS if r["key"] == key), None)
    if not definition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown reward.")
    state = db.query(UserReward).filter_by(user_id=user.id, reward_key=key).first()
    if not state or state.state != "UNLOCKED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This reward isn't unlocked yet.")
    state.state = "REDEEMED"
    state.redeemed_at = datetime.now(timezone.utc)
    db.commit()
    return RewardOut(
        key=definition["key"], title=definition["title"], description=definition["description"],
        icon=definition["icon"], requirement=definition["requirement"], state=state.state,
        unlocked_at=state.unlocked_at.isoformat() if state.unlocked_at else None,
        redeemed_at=state.redeemed_at.isoformat(),
    )
