import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class PasswordResetOtp(Base):
    """One emailed reset code — see PASSWORD_RESET_PLAN.md.

    Shape borrowed from braceletBackend's `otps` table (6 digits, a
    `purpose` column, an attempt ceiling), with three deliberate
    differences:

    - **Keyed on `user_id`, not a free-text address.** A later email change
      can't orphan a live code, and there is no second place where an
      address needs normalizing to match.
    - **The code is stored hashed**, never in plaintext. A readable
      six-digit credential sitting in a table is worth avoiding for the
      ten minutes it lives; braceletBackend stores plaintext, which is the
      one part of that implementation not to copy.
    - **Timezone-aware timestamps.** braceletBackend uses naive
      `datetime.utcnow()`; everything here is `datetime.now(timezone.utc)`
      against `DateTime(timezone=True)`, and mixing the two raises on
      comparison.
    """

    __tablename__ = "password_reset_otps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash = Column(String, nullable=False)
    purpose = Column(String(20), nullable=False, default="password_reset")
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    # Set the moment a reset succeeds, and on every superseded code when a
    # new one is requested. This is what makes a code single-use — there is
    # no separate is_used flag to keep in step with it.
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
