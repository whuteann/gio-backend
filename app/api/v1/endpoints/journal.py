import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.journal import JournalEntry
from app.models.user import User
from app.schemas.journal import JournalCreateRequest, JournalEntryOut, JournalInsightsOut
from app.services.ai_journal import classify_journal_entry
from app.services.gamification import today_utc
from app.services.journal import build_journal_insights, tag_journal_entry

from app.services.narrative import create_narrative_entry, get_or_create_narrative_profile, journal_memory, lock_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("/entries", response_model=list[JournalEntryOut])
def list_entries(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(JournalEntry).filter_by(user_id=user.id).order_by(JournalEntry.created_at.desc()).all()


@router.post("/entries", response_model=JournalEntryOut, status_code=201)
async def create_entry(payload: JournalCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lock_user(db, user)
    entry_id = uuid.uuid4()
    try:
        mood, theme = await classify_journal_entry(payload.content)
    except Exception:
        # Best-effort, same as the product-recommendation AI step — never
        # block saving a journal entry on this call failing/timing out.
        logger.exception("Journal mood/theme classification failed for entry %s — falling back to deterministic tagging.", entry_id)
        mood, theme = tag_journal_entry(str(entry_id))
    entry = JournalEntry(
        id=entry_id, user_id=user.id, content=payload.content, mood=mood, theme=theme,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.flush()
    profile = get_or_create_narrative_profile(db, user)
    create_narrative_entry(db, profile, source_type="JOURNAL", journal_entry_id=entry.id, summary=journal_memory(entry.content))
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/insights", response_model=JournalInsightsOut)
def get_insights(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entries = db.query(JournalEntry).filter_by(user_id=user.id).all()
    insights = build_journal_insights(entries, today_utc())
    return JournalInsightsOut(**insights)
