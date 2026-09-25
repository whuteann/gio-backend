import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.database import Base


class SubscriptionPayment(Base):
    """One row per Premium checkout attempt — see docs/behaviour_log_0009.md.
    Gio has no cart/order concept, so this collapses the xendit-handover
    reference's separate Order+Payment into a single row: the "order" here
    is simply "this user wants N months of Premium," fully described by
    `billing_cycle` + `amount`/`currency` (app/services/content.py::PREMIUM_PRICING).
    No inventory/reservation fields — there's nothing to reserve.
    """

    __tablename__ = "subscription_payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    billing_cycle = Column(String, nullable=False)  # MONTHLY | YEARLY
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, nullable=False, default="MYR")
    # Xendit's own invoice id (e.g. "65a1..."), set once the API call
    # succeeds — not a repurposed/renamed legacy field (contrast with the
    # reference implementation's `fiuu_transaction_id`, which its own
    # README flags as legacy baggage worth avoiding here).
    xendit_invoice_id = Column(String, nullable=True, index=True)
    # Gio-generated `external_id` sent to Xendit, e.g. "GIO-SUB-<uuid>" —
    # the fallback lookup key for the webhook when the invoice id alone
    # doesn't match (mirrors the reference's two-step lookup).
    reference_no = Column(String, nullable=False, unique=True)
    status = Column(String, nullable=False, default="PENDING")  # PENDING | COMPLETED | FAILED | EXPIRED
    invoice_url = Column(String, nullable=True)
    provider_data = Column(JSONB, nullable=True)  # full Xendit invoice response
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    paid_at = Column(DateTime(timezone=True), nullable=True)
