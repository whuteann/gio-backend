from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.user import SubscriptionOut

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("", response_model=SubscriptionOut)
def get_subscription(user: User = Depends(get_current_user)):
    return user.subscription


@router.post("/subscribe", response_model=SubscriptionOut)
def subscribe(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    sub = user.subscription
    sub.plan = "PREMIUM"
    sub.status = "ACTIVE"
    sub.starts_at = now
    sub.renews_at = now + timedelta(days=30)
    sub.expires_at = None
    sub.cancelled_at = None
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/cancel", response_model=SubscriptionOut)
def cancel(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    sub = user.subscription
    sub.status = "CANCELLED"
    sub.cancelled_at = now
    sub.expires_at = sub.renews_at or now
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/reactivate", response_model=SubscriptionOut)
def reactivate(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = user.subscription
    sub.status = "ACTIVE"
    sub.cancelled_at = None
    sub.expires_at = None
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/start-trial", response_model=SubscriptionOut)
def start_trial(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = user.subscription
    if sub.plan == "PREMIUM":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You're already on Premium.")
    if sub.trial_ends_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your free trial has already been used.")
    sub.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=7)
    db.commit()
    db.refresh(sub)
    return sub
