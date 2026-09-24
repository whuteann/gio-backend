import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.journal import JournalEntry
from app.models.user import User
from app.schemas.journal import JournalCreateRequest, JournalEntryOut, JournalInsightsOut
from app.services.gamification import today_utc
from app.services.journal import build_journal_insights, tag_journal_entry

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("/entries", response_model=list[JournalEntryOut])
def list_entries(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(JournalEntry).filter_by(user_id=user.id).order_by(JournalEntry.created_at.desc()).all()


@router.post("/entries", response_model=JournalEntryOut, status_code=201)
def create_entry(payload: JournalCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entry_id = uuid.uuid4()
    mood, theme = tag_journal_entry(str(entry_id))
    entry = JournalEntry(
        id=entry_id, user_id=user.id, content=payload.content, mood=mood, theme=theme,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/insights", response_model=JournalInsightsOut)
def get_insights(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entries = db.query(JournalEntry).filter_by(user_id=user.id).all()
    insights = build_journal_insights(entries, today_utc())
    return JournalInsightsOut(**insights)
