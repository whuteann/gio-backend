import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.personality import CorePersonality
from app.models.user import User
from app.schemas.core_personality import CalculateRequest, CorePersonalityResultOut
from app.services import languages
from app.services.content_language_jobs import enqueue_missing
from app.services.ai_personality import generate_core_personality_content
from app.services.numerology import (
    calculate_birthday_number,
    calculate_colour_weights,
    calculate_life_path_number,
    calculate_talent_number,
)

router = APIRouter(prefix="/core-personality", tags=["core-personality"])


@router.post("/calculate", response_model=CorePersonalityResultOut, status_code=status.HTTP_201_CREATED)
async def calculate(
    payload: CalculateRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Idempotent, not a 409: a user can legitimately end up back on the
    # birthdate step (reload, a crashed tab, retrying after a network blip)
    # after already generating one successfully — recalibration/regeneration
    # is separate future work, but simply handing back what already exists
    # is not that, it's just not erroring on a harmless retry.
    existing = db.query(CorePersonality).filter_by(user_id=user.id).first()
    if existing is not None:
        if user.onboarding_completed_at is None:
            user.onboarding_completed_at = datetime.now(timezone.utc)
            db.commit()
        enqueue_missing(db, "personalities", existing, user.preferred_language)
        db.commit()
        response.status_code = status.HTTP_200_OK
        return existing

    language = languages.normalize(payload.language or user.preferred_language)

    birthday_number = calculate_birthday_number(payload.date_of_birth)
    life_path_number = calculate_life_path_number(payload.date_of_birth)
    talent_number = calculate_talent_number(payload.date_of_birth)
    colour_weights = calculate_colour_weights(payload.date_of_birth, birthday_number, life_path_number, talent_number)

    content = await generate_core_personality_content(
        birthdate=payload.date_of_birth,
        birthday_number=birthday_number,
        life_path_number=life_path_number,
        talent_number=talent_number,
        colour_weights=colour_weights,
        language=language,
    )

    personality = CorePersonality(
        id=uuid.uuid4(),
        user_id=user.id,
        primary_language=language,
        generation_status="PARTIAL",
        languages_ready=[language],
        birthday_number=birthday_number,
        life_path_number=life_path_number,
        talent_number=talent_number,
        scarlet_score=colour_weights["scarlet"],
        russet_score=colour_weights["russet"],
        gold_score=colour_weights["gold"],
        forest_score=colour_weights["forest"],
        ocean_score=colour_weights["ocean"],
        **{
            f"title_{language}": content.title,
            f"subtitle_{language}": content.subtitle,
            f"overview_{language}": content.overview,
            f"birthday_number_points_{language}": [p.model_dump() for p in content.birthday_number_points],
            f"life_path_number_points_{language}": [p.model_dump() for p in content.life_path_number_points],
            f"talent_number_points_{language}": [p.model_dump() for p in content.talent_number_points],
            f"summary_{language}": content.summary,
        },
    )
    db.add(personality)
    user.birthdate = date.fromisoformat(payload.date_of_birth)
    # Onboarding is complete the moment generation succeeds — not deferred
    # to a separate "start my first reading" click, so a refresh anywhere
    # after this point never bounces the user back to /onboarding.
    if user.onboarding_completed_at is None:
        user.onboarding_completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(personality)

    enqueue_missing(db, "personalities", personality, user.preferred_language)
    db.commit()

    return personality


@router.get("/current", response_model=CorePersonalityResultOut)
def get_current(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The standalone /core-personality page's entry point — doesn't need
    an id, just "whatever this user has." No inner-reading/check-in
    dependency: Core Personality is self-contained (see
    docs/behaviour_log_0002.md), unlike the old page's colour section which
    borrowed from the latest recommendation."""
    personality = db.query(CorePersonality).filter_by(user_id=user.id).first()
    if personality is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Core Personality not yet calculated.")
    enqueue_missing(db, "personalities", personality, user.preferred_language)
    db.commit()
    return personality


@router.get("/{core_personality_id}/results", response_model=CorePersonalityResultOut)
def get_results(core_personality_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    personality = db.get(CorePersonality, core_personality_id)
    if personality is None or personality.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Core Personality not found.")
    enqueue_missing(db, "personalities", personality, user.preferred_language)
    db.commit()
    return personality
