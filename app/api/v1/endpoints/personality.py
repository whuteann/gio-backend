import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.personality import CorePersonality
from app.models.user import User
from app.schemas.personality import (
    BaselineOptionOut,
    BaselineQuestionOut,
    ColourAffinityOut,
    ColourBreakdownOut,
    CorePersonalityOut,
    NumerologyOut,
    OnboardingRequest,
    RecalibrateRequest,
    RecalibrateResponse,
)
from app.services.content import BASELINE_ASSESSMENT
from app.services.numerology import birthday_number, colour_affinity_scores, life_path_number, talent_number
from app.services.scoring import score_baseline, score_from_birthdate

router = APIRouter(prefix="/personality", tags=["personality"])

RECALIBRATION_COOLDOWN = timedelta(hours=24)


def _current_personality(db: Session, user_id) -> CorePersonality | None:
    return db.query(CorePersonality).filter_by(user_id=user_id, is_current=True).first()


@router.post("/onboarding", response_model=CorePersonalityOut)
def submit_onboarding(payload: OnboardingRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.birthdate is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Onboarding has already been completed.")
    user.birthdate = date.fromisoformat(payload.birthdate)

    scored = score_from_birthdate(payload.birthdate)
    personality = CorePersonality(
        id=uuid.uuid4(), user_id=user.id, version=1, is_current=True,
        assessment_version="birthdate-v1", generated_at=datetime.now(timezone.utc), recalibrated_at=None,
        **scored,
    )
    db.add(personality)
    db.commit()
    db.refresh(personality)
    return personality


@router.get("/current", response_model=CorePersonalityOut)
def get_current_personality(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    personality = _current_personality(db, user.id)
    if not personality:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Core Personality yet — complete onboarding first.")
    return personality


@router.get("/baseline-questions", response_model=list[BaselineQuestionOut])
def get_baseline_questions():
    return [
        BaselineQuestionOut(
            index=i, pillar=q["pillar"], prompt=q["prompt"],
            option_a=BaselineOptionOut(label=q["option_a"]["label"]),
            option_b=BaselineOptionOut(label=q["option_b"]["label"]),
        )
        for i, q in enumerate(BASELINE_ASSESSMENT)
    ]


@router.post("/recalibrate", response_model=RecalibrateResponse)
def recalibrate(payload: RecalibrateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    if user.core_personality_last_recalibrated_at:
        last = user.core_personality_last_recalibrated_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        eligible_at = last + RECALIBRATION_COOLDOWN
        if now < eligible_at:
            return RecalibrateResponse(ok=False, next_eligible_at=eligible_at)

    current = _current_personality(db, user.id)
    if current:
        current.is_current = False
    next_version = db.query(CorePersonality).filter_by(user_id=user.id).count() + 1

    new_id = uuid.uuid4()
    scored = score_baseline([a.model_dump() for a in payload.answers], seed_for_icon=str(new_id))
    personality = CorePersonality(
        id=new_id, user_id=user.id, version=next_version, is_current=True,
        assessment_version="baseline-v1", generated_at=now, recalibrated_at=now,
        **scored,
    )
    db.add(personality)
    user.core_personality_last_recalibrated_at = now
    db.commit()
    db.refresh(personality)
    return RecalibrateResponse(ok=True, personality=personality)


@router.get("/numerology", response_model=NumerologyOut)
def get_numerology(user: User = Depends(get_current_user)):
    if not user.birthdate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No birthdate on file — complete onboarding first.")
    bd = user.birthdate.isoformat()
    return NumerologyOut(
        life_path_number=life_path_number(bd),
        birthday_number=birthday_number(bd),
        talent_number=talent_number(bd),
    )


@router.get("/colour-breakdown", response_model=ColourBreakdownOut)
def get_colour_breakdown(user: User = Depends(get_current_user)):
    if not user.birthdate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No birthdate on file — complete onboarding first.")
    result = colour_affinity_scores(user.birthdate.isoformat())
    return ColourBreakdownOut(
        dominant_colour_key=result["dominant_colour_key"],
        scores=[ColourAffinityOut(**s) for s in result["scores"]],
    )
