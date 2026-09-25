from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CheckoutRequest(BaseModel):
    billing_cycle: str  # MONTHLY | YEARLY


class CheckoutResponse(BaseModel):
    payment_id: UUID
    invoice_url: str
    amount: float
    currency: str
    billing_cycle: str
    status: str


class SubscriptionPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    billing_cycle: str
    amount: float
    currency: str
    status: str
    invoice_url: str | None
    created_at: datetime
    paid_at: datetime | None
