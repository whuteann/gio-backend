import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.payment import SubscriptionPayment
from app.models.user import User
from app.schemas.payment import CheckoutRequest, CheckoutResponse, SubscriptionPaymentOut
from app.schemas.user import SubscriptionOut
from app.services import subscription_payment
from app.services.invoice import generate_invoice_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("", response_model=SubscriptionOut)
def get_subscription(user: User = Depends(get_current_user)):
    return user.subscription


@router.post("/checkout", response_model=CheckoutResponse, status_code=status.HTTP_201_CREATED)
def checkout(body: CheckoutRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a Xendit invoice for Premium — see docs/behaviour_log_0009.md.
    Replaces the old no-payment POST /subscribe: Premium is now only
    granted once the webhook below confirms payment, never on request."""
    payment = subscription_payment.checkout(db, user, body.billing_cycle.upper())
    return CheckoutResponse(
        payment_id=payment.id,
        invoice_url=payment.invoice_url or "",
        amount=float(payment.amount),
        currency=payment.currency,
        billing_cycle=payment.billing_cycle,
        status=payment.status,
    )


@router.post("/cancel", response_model=SubscriptionOut)
def cancel(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    sub = user.subscription
    sub.status = "CANCELLED"
    sub.cancelled_at = now
    sub.expires_at = sub.renews_at or now
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/reactivate", response_model=SubscriptionOut)
def reactivate(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = user.subscription
    sub.status = "ACTIVE"
    sub.cancelled_at = None
    sub.expires_at = None
    db.commit()
    db.refresh(sub)
    return sub


@router.post("/start-trial", response_model=SubscriptionOut)
def start_trial(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = user.subscription
    if sub.plan == "PREMIUM":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You're already on Premium.")
    if sub.trial_ends_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your free trial has already been used.")
    sub.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=7)
    db.commit()
    db.refresh(sub)
    return sub


@router.get("/payments", response_model=list[SubscriptionPaymentOut])
def list_payments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """A user's own billing/invoice history — see docs/behaviour_log_0009.md
    Phase 4.5. Simple and printable on the frontend; this is just the
    read path."""
    return (
        db.query(SubscriptionPayment)
        .filter_by(user_id=user.id)
        .order_by(SubscriptionPayment.created_at.desc())
        .all()
    )


@router.get("/payments/{payment_id}/invoice")
def get_payment_invoice(payment_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """A real PDF invoice for one payment, generated on the fly
    (app/services/invoice.py) — works identically for a real Xendit
    payment and a PAYMENT_GATEWAY_ENABLED=false bypass payment, since
    both are just SubscriptionPayment rows. `inline`, not `attachment`, so
    the frontend can open it in a new tab rather than force a download."""
    payment = db.query(SubscriptionPayment).filter_by(id=payment_id, user_id=user.id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")
    pdf_bytes = generate_invoice_pdf(payment, user)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="gio-invoice-{payment.reference_no}.pdf"'},
    )


@router.post("/webhook/xendit")
async def xendit_webhook(request: Request, db: Session = Depends(get_db)):
    """Xendit calls this directly — no user auth, protected by the
    x-callback-token header instead. Never treat a frontend redirect as
    proof of payment; only this webhook (or /sync-xendit below) grants
    Premium."""
    callback_token = request.headers.get("x-callback-token")
    payload = await request.json()
    logger.info("Xendit webhook for external_id=%s", payload.get("external_id"))
    return subscription_payment.handle_xendit_webhook(db, payload, callback_token)


@router.post("/sync-xendit/{payment_id}")
def sync_xendit_payment(payment_id: uuid.UUID, db: Session = Depends(get_db)):
    """Manually re-check a payment's Xendit status when a webhook was
    missed — operational endpoint, no auth dependency (mirrors the
    reference implementation's own equivalent)."""
    return subscription_payment.sync_payment(db, payment_id)
