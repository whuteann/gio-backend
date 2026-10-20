import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session, selectinload

from app.database import SessionLocal
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
from app.services.ai_outcome import generate_reading_outcome, generate_reading_secondary_language
from app.services.cascade import apply_reflection_side_effects
from app.services.content import AFFIRMATIONS, INSIGHTS, REFLECTION_QUESTIONS
from app.services.entitlement import INNER_READING_WEEKLY_FREE_LIMIT, inner_reading_weekly_count, is_premium_active
from app.services.narrative import lock_user, create_narrative_entry, get_or_create_narrative_profile, recent_narrative_summaries
from app.services.questions import get_or_generate_reading_question_set, next_inner_reading_increment
from app.services.scoring import dimension_averages, focus_label_for, normalize, reading_content_for_plan, resolve_focus_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inner-readings", tags=["inner-readings"])

_OTHER_LANGUAGE = {"en": "zh", "zh": "en"}

_LIFE_AREA_KEYS = ("work", "relationships", "personal_growth", "conflict_management")


async def _generate_secondary_language(reading_id: uuid.UUID, language: str) -> None:
    """Fills in the language the user did not ask for, after the response
    has already gone out (FastAPI BackgroundTasks) — same shape as
    core_personality.py::_generate_secondary_language, including its own
    short-lived session, since the request's is closed by the time this
    runs.

    A failure here is not fatal: the reading keeps its primary language and
    stays PARTIAL, and the frontend falls back to whichever language is
    present. It just never silently flips to READY.
    """
    db = SessionLocal()
    try:
        reading = db.get(InnerReading, reading_id)
        if reading is None:
            return

        primary = reading.primary_language or "en"
        content = await generate_reading_secondary_language(
            language=language,
            dims={
                "emotional_energy": reading.emotional_energy or 0,
                "mental_clarity": reading.mental_clarity or 0,
                "inner_pressure": reading.inner_pressure or 0,
                "grounding": reading.grounding or 0,
            },
            focus_label=focus_label_for(resolve_focus_key({
                "emotional_energy": reading.emotional_energy or 0,
                "mental_clarity": reading.mental_clarity or 0,
                "inner_pressure": reading.inner_pressure or 0,
                "grounding": reading.grounding or 0,
            })),
            primary_language=primary,
            primary_narrative=_field(reading, "narrative", primary) or "",
            primary_title=_field(reading, "title", primary) or "",
            primary_subtitle=_field(reading, "subtitle", primary) or "",
            primary_life_areas=_field(reading, "life_area_insights", primary) or {},
        )

        _set_field(reading, "narrative", language, content.narrative)
        _set_field(reading, "title", language, content.title)
        _set_field(reading, "subtitle", language, content.subtitle)
        _set_field(reading, "life_area_insights", language, {
            "work": content.life_area_work,
            "relationships": content.life_area_relationships,
            "personal_growth": content.life_area_personal_growth,
            "conflict_management": content.life_area_conflict_management,
        })
        reading.generation_status = "READY"
        db.commit()
        logger.info("Inner reading %s: %s version generated, now READY.", reading_id, language)
    except Exception:
        # Never let a background failure take down the worker — the reading
        # is already saved and usable in its primary language.
        logger.exception("Inner reading %s: %s version failed to generate.", reading_id, language)
        db.rollback()
    finally:
        db.close()


def _field(reading: InnerReading, name: str, language: str):
    """English lives in the unsuffixed column, Chinese in `<name>_zh` — the
    same layout CheckInSession uses, so there is no `_en` suffix to read."""
    return getattr(reading, name if language == "en" else f"{name}_zh")


def _set_field(reading: InnerReading, name: str, language: str, value) -> None:
    setattr(reading, name if language == "en" else f"{name}_zh", value)




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
async def submit_inner_reading(
    payload: InnerReadingSubmitRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    await run_in_threadpool(lock_user, db, user)
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

    # The language the reading is written in now, synchronously. Falls back
    # to the account's preference when the client doesn't say, so an older
    # client keeps working.
    language = payload.language if payload.language in ("en", "zh") else (user.preferred_language or "en")
    if language not in ("en", "zh"):
        language = "en"

    personality = user.core_personality
    personality_title = personality.title_en if personality else None

    narrative_profile = get_or_create_narrative_profile(db, user)
    recent_summaries = recent_narrative_summaries(db, narrative_profile)

    ai_outcome = await generate_reading_outcome(
        dims=dims, focus_label=focus_label, focus_key=focus_key, recent_narrative_summaries=recent_summaries,
        language=language,
    )
    affirmation_id = ai_outcome.affirmation_id.value
    insight_id = ai_outcome.insight_id.value
    reflection_question_id = ai_outcome.reflection_question_id.value

    reading = InnerReading(
        id=uuid.uuid4(), user_id=user.id, ordinal=_next_ordinal(db, user.id), status="COMPLETED",
        blueprint_version="reading-v1-ai",
        emotional_energy=dims["emotional_energy"], mental_clarity=dims["mental_clarity"],
        inner_pressure=dims["inner_pressure"], grounding=dims["grounding"],
        # insight/reflection_question/current_focus come from material that is
        # already bilingual — the curated library and the BilingualText fields
        # — so both languages are stored now and never need the second pass.
        insight=INSIGHTS[insight_id]["en"], insight_zh=INSIGHTS[insight_id]["zh"],
        reflection_question=REFLECTION_QUESTIONS[reflection_question_id]["en"],
        reflection_question_zh=REFLECTION_QUESTIONS[reflection_question_id]["zh"],
        current_focus=ai_outcome.current_focus.en, current_focus_zh=ai_outcome.current_focus.zh,
        result_summary=f"Inner Reading — {ai_outcome.current_focus.en}",
        result_summary_zh=f"内在解读 — {ai_outcome.current_focus.zh}",
        primary_language=language,
        generation_status="PARTIAL",
        started_at=now, completed_at=now, created_at=now,
    )
    # The generated body goes into whichever language column was asked for;
    # the other is filled by the background task below.
    _set_field(reading, "narrative", language, ai_outcome.narrative)
    _set_field(reading, "title", language, ai_outcome.title)
    _set_field(reading, "subtitle", language, ai_outcome.subtitle)
    _set_field(reading, "life_area_insights", language, {
        "work": ai_outcome.life_area_work,
        "relationships": ai_outcome.life_area_relationships,
        "personal_growth": ai_outcome.life_area_personal_growth,
        "conflict_management": ai_outcome.life_area_conflict_management,
    })
    db.add(reading)
    db.flush()

    for i, a in enumerate(payload.answers):
        db.add(InnerReadingAnswer(
            inner_reading_id=reading.id, dimension=a.dimension, question_text=a.question_text,
            answer_value=a.value, normalized_value=normalize(a.value), order_index=i, answered_at=now,
        ))
    db.flush()

    outcome = await run_in_threadpool(
        apply_reflection_side_effects, db, user, quest_key="INNER_READING", xp_amount=25, dims=dims, source_type="INNER_READING",
        inner_reading_id=reading.id,
        core_personality_id=personality.id if personality else None,
        personality_title=personality_title,
        narrative_content={
            "insight": INSIGHTS[insight_id],
            "reflection_question": REFLECTION_QUESTIONS[reflection_question_id],
            "reminder": {"en": ai_outcome.reminder.en, "zh": ai_outcome.reminder.zh},
            "current_focus": {"en": ai_outcome.current_focus.en, "zh": ai_outcome.current_focus.zh},
            "friendly_advice": {"en": ai_outcome.friendly_advice.en, "zh": ai_outcome.friendly_advice.zh},
            "affirmation": AFFIRMATIONS[affirmation_id],
        },
        affirmation_id=affirmation_id, insight_id=insight_id, reflection_question_id=reflection_question_id,
    )

    narrative_entry = create_narrative_entry(
        db, narrative_profile, source_type="INNER_READING", summary=ai_outcome.narrative_summary,
        inner_reading_id=reading.id,
    )
    reading.narrative_entry_id = narrative_entry.id

    user.last_inner_reading_at = now
    user.inner_reading_count_today = increment

    db.commit()

    # Queued after the commit, so the row the task loads in its own session
    # definitely exists. Runs once the response has been sent.
    background_tasks.add_task(_generate_secondary_language, reading.id, _OTHER_LANGUAGE[language])

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
