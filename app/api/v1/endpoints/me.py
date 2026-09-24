from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.user import ChangePasswordRequest, MeOut, UpdateProfileRequest, UserOut

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeOut)
def get_me(user: User = Depends(get_current_user)):
    return MeOut(user=UserOut.model_validate(user), subscription=user.subscription)


@router.patch("", response_model=UserOut)
def update_me(payload: UpdateProfileRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.preferred_language is not None:
        user.preferred_language = payload.preferred_language
    if payload.timezone is not None:
        user.timezone = payload.timezone
    db.commit()
    db.refresh(user)
    return user


@router.patch("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(payload: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Authenticated self-service change, not the "forgot password" flow —
    # the caller already proved identity via their JWT, so no current-
    # password or email-token step is required here (see docs/dev_log_0001.md
    # for why the separate, unauthenticated forgot-password flow is still a
    # deliberate gap).
    user.password_hash = hash_password(payload.new_password)
    db.commit()
