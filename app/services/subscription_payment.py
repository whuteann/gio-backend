"""Premium checkout via Xendit — see docs/behaviour_log_0009.md.

Ported from GioMembershipPlatform/xendit-handover/'s
`create_xendit_invoice_service`/`handle_xendit_webhook_service`, adapted
from an ecommerce order to a subscription: there's no cart/inventory here,
just "this user wants N months of Premium" (app/services/content.py::PREMIUM_PRICING).
No refunds, no cancellations, no auto-renewal — a Premium period simply
expires; resubscribing means paying again through this same checkout.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.payment import SubscriptionPayment
from app.models.user import User
from app.services import xendit_client
from app.services.content import PREMIUM_PRICING
from app.config import settings

logger = logging.getLogger(__name__)

BILLING_CYCLE_DAYS = {"MONTHLY": 30, "YEARLY": 365}


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _bypass_checkout(db: Session, user: User, billing_cycle: str, amount: Decimal, currency: str) -> SubscriptionPayment:
    """PAYMENT_GATEWAY_ENABLED=false path — no Xendit call, no invoice, no
    money collected. Grants Premium immediately and still writes a real
    SubscriptionPayment row (status COMPLETED, no xendit_invoice_id) so
    billing history and _apply_premium's normal state transition both stay
    accurate — the only thing skipped is the actual payment collection."""
    now = datetime.now(timezone.utc)
    payment = SubscriptionPayment(
        user_id=user.id,
        billing_cycle=billing_cycle,
        amount=amount,
        currency=currency,
        xendit_invoice_id=None,
        reference_no=f"GIO-SUB-BYPASS-{uuid.uuid4()}",
        status="COMPLETED",
        invoice_url=settings.xendit_success_redirect_url,
        provider_data={"bypass": True, "reason": "PAYMENT_GATEWAY_ENABLED=false"},
        paid_at=now,
    )
    db.add(payment)
    _apply_premium(db, user, billing_cycle, now)
    db.commit()
    db.refresh(payment)
    logger.info("Payment gateway disabled — granted Premium to user=%s with no payment collected.", user.id)
    return payment


def checkout(db: Session, user: User, billing_cycle: str) -> SubscriptionPayment:
    if billing_cycle not in PREMIUM_PRICING:
        raise HTTPException(status_code=400, detail="Invalid billing_cycle — must be MONTHLY or YEARLY")

    pricing = PREMIUM_PRICING[billing_cycle]
    amount = pricing["amount"]
    currency = pricing["currency"]

    # Lock this user's row for the duration of this transaction — without
    # it, two rapid "Subscribe" taps both pass the checks below and both
    # call Xendit, creating two invoices. Mirrors the reference
    # implementation's order-row lock; Gio has no order to lock, so this
    # locks the user instead.
    db.query(User).filter(User.id == user.id).with_for_update().first()

    if not settings.payment_gateway_enabled:
        return _bypass_checkout(db, user, billing_cycle, amount, currency)

    existing = (
        db.query(SubscriptionPayment)
        .filter_by(user_id=user.id, status="PENDING")
        .order_by(SubscriptionPayment.created_at.desc())
        .first()
    )
    if existing and existing.billing_cycle == billing_cycle and _money(existing.amount) == amount:
        return existing
    if existing:
        existing.status = "FAILED"

    reference_no = f"GIO-SUB-{uuid.uuid4()}"
    description = f"Gio Premium — {billing_cycle.title()} subscription"

    invoice = xendit_client.create_invoice(
        external_id=reference_no,
        amount=float(amount),
        currency=currency,
        payer_email=user.email,
        payer_name=user.display_name,
        description=description,
        success_redirect_url=settings.xendit_success_redirect_url,
        failure_redirect_url=settings.xendit_failure_redirect_url,
    )

    payment = SubscriptionPayment(
        user_id=user.id,
        billing_cycle=billing_cycle,
        amount=amount,
        currency=currency,
        xendit_invoice_id=invoice.get("id"),
        reference_no=reference_no,
        status="PENDING",
        invoice_url=invoice.get("invoice_url"),
        provider_data=invoice,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def _apply_premium(db: Session, user: User, billing_cycle: str, now: datetime) -> None:
    """The paid state transition — reproduces subscription.py::subscribe()'s
    shape, now billing-cycle-aware and gated on a real payment instead of
    granted on request."""
    sub = user.subscription
    sub.plan = "PREMIUM"
    sub.status = "ACTIVE"
    if sub.starts_at is None:
        sub.starts_at = now
    sub.renews_at = now + timedelta(days=BILLING_CYCLE_DAYS[billing_cycle])
    sub.expires_at = None
    sub.cancelled_at = None


def handle_xendit_webhook(db: Session, payload: dict[str, Any], callback_token: str | None) -> dict:
    if not settings.xendit_webhook_token:
        logger.error("Xendit webhook received but XENDIT_WEBHOOK_TOKEN is not configured — refusing.")
        raise HTTPException(status_code=401, detail="Webhook token not configured on this server")
    if callback_token != settings.xendit_webhook_token:
        logger.warning("Xendit webhook: invalid token")
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    xendit_invoice_id = payload.get("id")
    external_id = payload.get("external_id")
    xendit_status = (payload.get("status") or "").upper()

    if not xendit_invoice_id:
        raise HTTPException(status_code=400, detail="Missing invoice id in webhook")

    payment = db.query(SubscriptionPayment).filter_by(xendit_invoice_id=xendit_invoice_id).first()
    if not payment and external_id:
        payment = db.query(SubscriptionPayment).filter_by(reference_no=external_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Subscription payment record not found")

    # Idempotent — a webhook can legitimately be redelivered by Xendit.
    if payment.status == "COMPLETED":
        return {"status": "ok", "payment_id": str(payment.id), "already_processed": True}

    payment.provider_data = payload

    if xendit_status in ("PAID", "SETTLED"):
        paid_amount = _money(payload.get("paid_amount") or payload.get("amount") or payment.amount)
        expected_amount = _money(payment.amount)
        if paid_amount != expected_amount:
            logger.error(
                "Xendit webhook amount mismatch: payment_id=%s expected=%s received=%s",
                payment.id, expected_amount, paid_amount,
            )
            raise HTTPException(status_code=400, detail="Xendit paid amount does not match expected amount")

        paid_at_str = payload.get("paid_at")
        if paid_at_str:
            try:
                payment.paid_at = datetime.fromisoformat(paid_at_str.replace("Z", "+00:00"))
            except ValueError:
                payment.paid_at = datetime.now(timezone.utc)
        else:
            payment.paid_at = datetime.now(timezone.utc)

        payment.status = "COMPLETED"
        user = db.query(User).filter_by(id=payment.user_id).first()
        _apply_premium(db, user, payment.billing_cycle, payment.paid_at)
        db.commit()
        return {"status": "ok", "payment_id": str(payment.id)}

    if xendit_status == "EXPIRED":
        payment.status = "FAILED"
        db.commit()
        return {"status": "ok", "payment_id": str(payment.id)}

    db.commit()
    return {"status": "ok", "payment_id": str(payment.id)}


def sync_payment(db: Session, payment_id: uuid.UUID) -> dict:
    """Manually query Xendit for a payment's latest invoice status and
    settle it through the same handler — for a missed webhook. No auth
    dependency at the route level (operational endpoint), same caveat the
    reference implementation gives its own version."""
    payment = db.query(SubscriptionPayment).filter_by(id=payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Subscription payment not found")
    if not payment.xendit_invoice_id:
        raise HTTPException(status_code=400, detail="Payment has no Xendit invoice id")

    invoice = xendit_client.get_invoice(payment.xendit_invoice_id)
    return handle_xendit_webhook(db, invoice, callback_token=settings.xendit_webhook_token)
