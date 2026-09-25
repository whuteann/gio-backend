"""Thin Xendit Invoices API client — see docs/behaviour_log_0009.md.

Ported from GioMembershipPlatform/xendit-handover/'s proven
`create_xendit_invoice_service`/`_xendit_auth` pattern (a working
integration in a sibling project), trimmed to exactly what Gio's
subscription checkout needs: no order/cart, no inventory, no chatbot path.

Xendit has no separate sandbox hostname — test vs. live is entirely which
secret key is configured (`xnd_development_...` vs `xnd_production_...`),
both against this same base URL. `settings.xendit_environment` is never
used here; it's a cosmetic UI/log indicator only (Phase 5).
"""

from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings

XENDIT_BASE_URL = "https://api.xendit.co"
XENDIT_INVOICE_DURATION_SECONDS = 86400  # 24 hours


def _auth() -> httpx.BasicAuth:
    return httpx.BasicAuth(username=settings.xendit_secret_key, password="")


def create_invoice(
    *,
    external_id: str,
    amount: float,
    currency: str,
    payer_email: str,
    payer_name: str,
    description: str,
    success_redirect_url: str,
    failure_redirect_url: str,
) -> dict[str, Any]:
    """POST /v2/invoices. Raises HTTPException(502) on any Xendit-side or
    network failure — mirrors the reference implementation's own handling,
    since a payment initiation failing is always the caller's problem to
    surface, never something to silently swallow."""
    payload = {
        "external_id": external_id,
        "amount": amount,
        "payer_email": payer_email,
        "description": description,
        "invoice_duration": XENDIT_INVOICE_DURATION_SECONDS,
        "customer": {"given_names": payer_name, "email": payer_email},
        "customer_notification_preference": {
            "invoice_created": ["email"],
            "invoice_reminder": ["email"],
            "invoice_paid": ["email"],
        },
        "success_redirect_url": success_redirect_url,
        "failure_redirect_url": failure_redirect_url,
        "currency": currency,
    }
    try:
        response = httpx.post(f"{XENDIT_BASE_URL}/v2/invoices", auth=_auth(), json=payload, timeout=30.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json()
        except Exception:
            detail = e.response.text
        raise HTTPException(status_code=502, detail=f"Xendit error: {detail}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach Xendit: {e}")


def get_invoice(invoice_id: str) -> dict[str, Any]:
    """GET /v2/invoices/{id} — for the manual sync/reconciliation path."""
    try:
        response = httpx.get(f"{XENDIT_BASE_URL}/v2/invoices/{invoice_id}", auth=_auth(), timeout=15.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Xendit error: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach Xendit: {e}")
