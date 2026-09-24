from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JournalCreateRequest(BaseModel):
    content: str


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    mood: str
    theme: str
    created_at: datetime


class JournalInsightsOut(BaseModel):
    entries_this_week: int
    entries_delta: int
    top_mood: str | None
    top_theme: str | None
