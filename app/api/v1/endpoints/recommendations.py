import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.dependencies import get_current_user, get_db
from app.models.recommendation import RecommendationProfile
from app.models.user import User
from app.schemas.recommendation import RecommendationOut
from app.services.content import COLOURS
from app.services.entitlement import is_premium_active
from app.services.recommendation import ensure_recommendation

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _serialize(profile: RecommendationProfile) -> RecommendationOut:
    colour = COLOURS[profile.colour_key]
    return RecommendationOut(
        id=profile.id, current_focus=profile.current_focus, current_focus_zh=profile.current_focus_zh,
        summary=profile.summary, summary_zh=profile.summary_zh,
        colour_key=colour["key"], colour_name=colour["name"], colour_name_zh=colour["name_zh"], colour_swatch=colour["swatch"],
        material_affinity=profile.material_affinity, letter_en=profile.letter_en, letter_zh=profile.letter_zh,
        status=profile.status, generated_at=profile.generated_at, items=profile.items,
    )


@router.get("/latest", response_model=RecommendationOut)
def get_latest_recommendation(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Today's recommendation, generated on the spot if there isn't one.

    Deliberately a sync `def`: ensure_recommendation reaches
    _refresh_product_items, which calls asyncio.run() internally. That throws
    inside a running event loop, so this must stay on FastAPI's threadpool
    rather than becoming `async def`.

    404 now means one thing only — this account has never completed a
    check-in or Inner Reading, so there is no inner state to build from.
    """
    profile = ensure_recommendation(db, user)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complete a check-in or Inner Reading first.")
    db.commit()
    db.refresh(profile)
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


@router.get("/{recommendation_id}", response_model=RecommendationOut)
def get_recommendation(recommendation_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The full brochure/detail view (see docs/recommendation_engine.md) —
    one specific day's recommendation by id, not just "latest". Registered
    after /latest and the bare list route so those literal paths are
    matched first."""
    profile = (
        db.query(RecommendationProfile)
        .options(selectinload(RecommendationProfile.items))
        .filter_by(id=recommendation_id, user_id=user.id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found.")
    return _serialize(profile)
