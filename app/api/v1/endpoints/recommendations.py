from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.dependencies import get_current_user, get_db
from app.models.recommendation import RecommendationProfile
from app.models.user import User
from app.schemas.recommendation import RecommendationOut
from app.services.content import COLOURS
from app.services.entitlement import is_premium_active

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _serialize(profile: RecommendationProfile) -> RecommendationOut:
    colour = COLOURS[profile.colour_key]
    return RecommendationOut(
        id=profile.id, current_focus=profile.current_focus, summary=profile.summary,
        colour_key=colour["key"], colour_name=colour["name"], colour_swatch=colour["swatch"],
        status=profile.status, generated_at=profile.generated_at, items=profile.items,
    )


@router.get("/latest", response_model=RecommendationOut)
def get_latest_recommendation(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = (
        db.query(RecommendationProfile)
        .options(selectinload(RecommendationProfile.items))
        .filter_by(user_id=user.id)
        .order_by(RecommendationProfile.generated_at.desc())
        .first()
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complete a check-in or Inner Reading first.")
    return _serialize(profile)


@router.get("", response_model=list[RecommendationOut])
def list_recommendations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The "pattern" view (item 3): free sees today's colour only, Premium
    sees the full colour-over-time history."""
    query = (
        db.query(RecommendationProfile)
        .options(selectinload(RecommendationProfile.items))
        .filter_by(user_id=user.id)
        .order_by(RecommendationProfile.generated_at.desc())
    )
    if not is_premium_active(user.subscription):
        query = query.limit(1)
    return [_serialize(p) for p in query.all()]
