import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.dependencies import get_current_user, get_db
from app.models.personality import CorePersonality
from app.models.user import User
from app.schemas.core_personality import CalculateRequest, CorePersonalityResultOut
from app.services.ai_personality import generate_core_personality_content
from app.services.numerology import (
    calculate_birthday_number,
    calculate_colour_weights,
    calculate_life_path_number,
    calculate_talent_number,
)

router = APIRouter(prefix="/core-personality", tags=["core-personality"])

_OTHER_LANGUAGE = {"en": "zh", "zh": "en"}


async def _generate_secondary_language(core_personality_id: uuid.UUID, birthdate: str, language: str) -> None:
    """Runs after the response is sent (FastAPI BackgroundTasks) — its own
    short-lived DB session, since the request's session is already closed
    by the time this runs."""
    db = SessionLocal()
    try:
        personality = db.get(CorePersonality, core_personality_id)
        if personality is None:
            return

        content = await generate_core_personality_content(
            birthdate=birthdate,
            birthday_number=personality.birthday_number,
            life_path_number=personality.life_path_number,
            talent_number=personality.talent_number,
            colour_weights={
                "scarlet": personality.scarlet_score,
                "russet": personality.russet_score,
                "gold": personality.gold_score,
                "forest": personality.forest_score,
                "ocean": personality.ocean_score,
            },
            language=language,
        )

        setattr(personality, f"title_{language}", content.title)
        setattr(personality, f"subtitle_{language}", content.subtitle)
        setattr(personality, f"overview_{language}", content.overview)
        setattr(personality, f"birthday_number_content_{language}", content.birthday_number_content)
        setattr(personality, f"life_path_number_content_{language}", content.life_path_number_content)
        setattr(personality, f"talent_number_content_{language}", content.talent_number_content)
        setattr(personality, f"summary_{language}", content.summary)
        personality.generation_status = "READY"
        db.commit()
    finally:
        db.close()


@router.post("/calculate", response_model=CorePersonalityResultOut, status_code=status.HTTP_201_CREATED)
async def calculate(
    payload: CalculateRequest,
    background_tasks: BackgroundTasks,
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
        response.status_code = status.HTTP_200_OK
        return existing

    language = payload.language if payload.language in ("en", "zh") else "en"

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
            f"birthday_number_content_{language}": content.birthday_number_content,
            f"life_path_number_content_{language}": content.life_path_number_content,
            f"talent_number_content_{language}": content.talent_number_content,
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

    background_tasks.add_task(
        _generate_secondary_language, personality.id, payload.date_of_birth, _OTHER_LANGUAGE[language]
    )

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
    return personality


@router.get("/{core_personality_id}/results", response_model=CorePersonalityResultOut)
def get_results(core_personality_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    personality = db.get(CorePersonality, core_personality_id)
    if personality is None or personality.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Core Personality not found.")
    return personality
