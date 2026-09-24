import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.dependencies import get_current_user, get_db
from app.models.reflection import CheckInAnswer, CheckInSession, InnerStateSnapshot
from app.models.user import User
from app.schemas.reflection import (
    CheckInResultsOut,
    CheckInSessionOut,
    CheckInSubmitRequest,
    CheckInSubmitResponse,
    InnerStateSnapshotOut,
    OutcomeOut,
    QuestionOut,
    QuestionSetOut,
)
from app.services import gamification as gam
from app.services.ai_outcome import generate_checkin_outcome
from app.services.cascade import apply_reflection_side_effects
from app.services.entitlement import check_in_history_cutoff
from app.services.narrative import create_narrative_entry, get_or_create_narrative_profile, recent_narrative_summaries
from app.services.questions import get_or_generate_checkin_question_set, next_check_in_increment
from app.services.scoring import dimension_averages, focus_label_for, normalize, resolve_focus_key

router = APIRouter(prefix="/check-ins", tags=["check-ins"])


@router.get("/questions", response_model=QuestionSetOut)
async def get_questions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    increment = next_check_in_increment(user)
    question_set = await get_or_generate_checkin_question_set(db, gam.today_utc(), increment)
    db.commit()
    return QuestionSetOut(
        blueprint_version=question_set.blueprint_version,
        questions=[QuestionOut(**q) for q in question_set.questions],
    )


@router.post("", response_model=CheckInSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_check_in(payload: CheckInSubmitRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)

    # Resolved before any mutation — next_check_in_increment reads the
    # user's *current* stored last_check_in_at/check_in_count_today.
    increment = next_check_in_increment(user)

    session = CheckInSession(
        id=uuid.uuid4(), user_id=user.id, source="WEB", status="COMPLETED",
        blueprint_version="checkin-v1-demo", private_note=payload.private_note,
        started_at=now, completed_at=now,
    )
    db.add(session)
    db.flush()

    normalized_answers = []
    for i, a in enumerate(payload.answers):
        normalized_value = normalize(a.value)
        db.add(CheckInAnswer(
            check_in_session_id=session.id, dimension=a.dimension, question_text=a.question_text,
            answer_value=a.value, normalized_value=normalized_value, order_index=i, answered_at=now,
        ))
        normalized_answers.append({"dimension": a.dimension, "normalized_value": normalized_value})
    db.flush()

    dims = dimension_averages(normalized_answers)
    focus_key = resolve_focus_key(dims)
    focus_label = focus_label_for(focus_key)

    personality = user.core_personality
    personality_title = personality.title_en if personality else None

    narrative_profile = get_or_create_narrative_profile(db, user)
    recent_summaries = recent_narrative_summaries(db, narrative_profile)

    ai_outcome = await generate_checkin_outcome(
        dims=dims, focus_label=focus_label, recent_narrative_summaries=recent_summaries,
    )

    outcome = apply_reflection_side_effects(
        db, user, quest_key="CHECK_IN", xp_amount=10, dims=dims, source_type="CHECK_IN",
        check_in_session_id=session.id,
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
        db, narrative_profile, source_type="CHECK_IN", summary=ai_outcome.narrative_summary,
        check_in_session_id=session.id,
    )
    # Deterministic, not AI — see docs/behaviour_log_0006.md's resolved
    # open question: NarrativeEntry.summary is the one AI-facing memory
    # record for this event; CheckInSession.summary is just a short label.
    session.summary = f"Check-in — {focus_label}"
    session.narrative_entry_id = narrative_entry.id

    user.last_check_in_at = now
    user.check_in_count_today = increment

    db.commit()

    return CheckInSubmitResponse(
        session_id=session.id,
        outcome=OutcomeOut(
            xp_awarded=outcome["xp_awarded"], bonus_awarded=outcome["bonus_awarded"],
            milestone=outcome["milestone"], new_badges=outcome["new_badges"],
        ),
    )


@router.get("", response_model=list[CheckInSessionOut])
def list_check_ins(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cutoff = check_in_history_cutoff(user.subscription)
    query = db.query(CheckInSession).options(selectinload(CheckInSession.answers)).filter_by(user_id=user.id)
    if cutoff:
        query = query.filter(CheckInSession.started_at >= cutoff)
    return query.order_by(CheckInSession.started_at.desc()).all()


@router.get("/{session_id}", response_model=CheckInSessionOut)
def get_check_in(session_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = (
        db.query(CheckInSession)
        .options(selectinload(CheckInSession.answers))
        .filter_by(id=session_id, user_id=user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check-in not found.")
    return session


@router.get("/{session_id}/results", response_model=CheckInResultsOut)
def get_check_in_results(session_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = (
        db.query(CheckInSession)
        .options(selectinload(CheckInSession.answers))
        .filter_by(id=session_id, user_id=user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check-in not found.")

    snapshot = db.query(InnerStateSnapshot).filter_by(check_in_session_id=session.id).first()
    return CheckInResultsOut(
        session=CheckInSessionOut.model_validate(session),
        snapshot=InnerStateSnapshotOut.from_model(snapshot) if snapshot else None,
    )
