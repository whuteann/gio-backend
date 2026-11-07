import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class ContentLanguageJob(Base):
    __tablename__ = "content_language_jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String, nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    language = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    locked_at = Column(DateTime(timezone=True), nullable=True)
    error_type = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        UniqueConstraint("kind", "entity_id", "language", name="uq_content_language_job"),
        Index("ix_content_language_job_due", "status", "next_attempt_at"),
    )
