import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.dependencies import get_current_user, get_db
from app.models.reflection import InnerReading, InnerReadingAnswer
from app.models.user import User
from app.schemas.reflection import (
    InnerReadingOut,
    InnerReadingSubmitRequest,
    InnerReadingSubmitResponse,
    OutcomeOut,
    QuestionOut,
    QuestionSetOut,
)
from app.services import gamification as gam
from app.services.ai_outcome import generate_reading_outcome
from app.services.cascade import apply_reflection_side_effects
from app.services.entitlement import INNER_READING_WEEKLY_FREE_LIMIT, inner_reading_weekly_count, is_premium_active
from app.services.narrative import create_narrative_entry, get_or_create_narrative_profile, recent_narrative_summaries
from app.services.questions import get_or_generate_reading_question_set, next_inner_reading_increment
from app.services.scoring import dimension_averages, focus_label_for, normalize, reading_content_for_plan, resolve_focus_key

router = APIRouter(prefix="/inner-readings", tags=["inner-readings"])


def _serialize(reading: InnerReading, premium: bool) -> InnerReadingOut:
    base = InnerReadingOut.model_validate(reading)
    return base.model_copy(update=reading_content_for_plan(reading, premium))


def _next_ordinal(db: Session, user_id: uuid.UUID) -> int:
    return db.query(InnerReading).filter_by(user_id=user_id).count() + 1


@router.get("/questions", response_model=QuestionSetOut)
async def get_questions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    increment = next_inner_reading_increment(user)
    question_set = await get_or_generate_reading_question_set(db, gam.today_utc(), increment)
    db.commit()
    return QuestionSetOut(
        blueprint_version=question_set.blueprint_version,
        questions=[QuestionOut(**q) for q in question_set.questions],
    )


@router.post("", response_model=InnerReadingSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_inner_reading(payload: InnerReadingSubmitRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    premium = is_premium_active(user.subscription)
    if not premium and inner_reading_weekly_count(db, user.id) >= INNER_READING_WEEKLY_FREE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Free plan includes 3 Inner Readings per 7 days. Upgrade to Premium for unlimited.",
        )

    now = datetime.now(timezone.utc)
    # Resolved before any mutation — mirrors checkins.py::submit_check_in.
    increment = next_inner_reading_increment(user)

    normalized_answers = []
    for a in payload.answers:
        normalized_answers.append({"dimension": a.dimension, "normalized_value": normalize(a.value)})
    dims = dimension_averages(normalized_answers)
    focus_key = resolve_focus_key(dims)
    focus_label = focus_label_for(focus_key)

    personality = user.core_personality
    personality_title = personality.title_en if personality else None

    narrative_profile = get_or_create_narrative_profile(db, user)
    recent_summaries = recent_narrative_summaries(db, narrative_profile)

    ai_outcome = await generate_reading_outcome(
        dims=dims, focus_label=focus_label, recent_narrative_summaries=recent_summaries,
    )

    reading = InnerReading(
        id=uuid.uuid4(), user_id=user.id, ordinal=_next_ordinal(db, user.id), status="COMPLETED",
        blueprint_version="reading-v1-ai",
        emotional_energy=dims["emotional_energy"], mental_clarity=dims["mental_clarity"],
        inner_pressure=dims["inner_pressure"], grounding=dims["grounding"],
        result_summary=f"Inner Reading — {focus_label}",
        narrative=ai_outcome.narrative,
        insight=ai_outcome.insight, reflection_question=ai_outcome.reflection_question,
        title=ai_outcome.title, subtitle=ai_outcome.subtitle,
        life_area_insights={
            "work": ai_outcome.life_area_work,
            "relationships": ai_outcome.life_area_relationships,
            "personal_growth": ai_outcome.life_area_personal_growth,
            "conflict_management": ai_outcome.life_area_conflict_management,
        },
        started_at=now, completed_at=now, created_at=now,
    )
    db.add(reading)
    db.flush()

    for i, a in enumerate(payload.answers):
        db.add(InnerReadingAnswer(
            inner_reading_id=reading.id, dimension=a.dimension, question_text=a.question_text,
            answer_value=a.value, normalized_value=normalize(a.value), order_index=i, answered_at=now,
        ))
    db.flush()

    outcome = apply_reflection_side_effects(
        db, user, quest_key="INNER_READING", xp_amount=25, dims=dims, source_type="INNER_READING",
        inner_reading_id=reading.id,
        core_personality_id=personality.id if personality else None,
        personality_title=personality_title,
        narrative_content={
            "insight": ai_outcome.insight,
            "reflection_question": ai_outcome.reflection_question,
            "reminder": ai_outcome.reminder,
            "current_focus": ai_outcome.current_focus,
            "friendly_advice": ai_outcome.friendly_advice,
            "affirmation": ai_outcome.affirmation,
        },
    )

    narrative_entry = create_narrative_entry(
        db, narrative_profile, source_type="INNER_READING", summary=ai_outcome.narrative_summary,
        inner_reading_id=reading.id,
    )
    reading.narrative_entry_id = narrative_entry.id

    user.last_inner_reading_at = now
    user.inner_reading_count_today = increment

    db.commit()

    return InnerReadingSubmitResponse(
        reading_id=reading.id,
        outcome=OutcomeOut(
            xp_awarded=outcome["xp_awarded"], bonus_awarded=outcome["bonus_awarded"],
            milestone=outcome["milestone"], new_badges=outcome["new_badges"],
        ),
    )


@router.get("", response_model=list[InnerReadingOut])
def list_inner_readings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    premium = is_premium_active(user.subscription)
    readings = (
        db.query(InnerReading)
        .filter_by(user_id=user.id)
        .order_by(InnerReading.created_at.desc())
        .all()
    )
    return [_serialize(r, premium) for r in readings]


@router.get("/{reading_id}", response_model=InnerReadingOut)
def get_inner_reading(reading_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reading = (
        db.query(InnerReading)
        .options(selectinload(InnerReading.answers))
        .filter_by(id=reading_id, user_id=user.id)
        .first()
    )
    if not reading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inner Reading not found.")
    return _serialize(reading, is_premium_active(user.subscription))
