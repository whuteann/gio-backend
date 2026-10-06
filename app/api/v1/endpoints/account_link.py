import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.link_token import (
    PURPOSE_ADMIN_UNLINK,
    PURPOSE_SSO_TO_AUREN,
    PURPOSE_SSO_TO_GIO,
    PURPOSE_VERIFY_AUREN,
    PURPOSE_VERIFY_GIO,
    issue_link_token,
    issue_sso_token,
    verify_link_token,
)
from app.core.security import create_access_token, create_refresh_token, verify_password
from app.dependencies import get_current_user, get_db
from app.models.user import Subscription, User
from app.schemas.account_link import (
    AdminUserListItem,
    AdminUserListResponse,
    AuthenticateRequest,
    AuthenticateResponse,
    CheckPhoneRequest,
    CheckPhoneResponse,
    ConfirmRequest,
    ConfirmResponse,
    HandoffResponse,
    IssueAssertionResponse,
    LinkStatusResponse,
    SsoExchangeRequest,
    UnlinkRequest,
    UnlinkResponse,
)
from app.schemas.auth import TokenResponse
from app.services.account_link import strip_phone_number

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account-link", tags=["account-link"])


def _require_service_key(request: Request) -> None:
    secret = request.headers.get("X-Service-Key", "")
    if not settings.internal_link_secret or secret != settings.internal_link_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid service key")


@router.post("/check-phone", response_model=CheckPhoneResponse)
def check_phone(payload: CheckPhoneRequest, db: Session = Depends(get_db)):
    phone = strip_phone_number(payload.phone_number)
    user = db.query(User).filter(User.phone_number == phone).first()
    return CheckPhoneResponse(exists=user is not None)


@router.post("/authenticate", response_model=AuthenticateResponse)
def authenticate(payload: AuthenticateRequest, db: Session = Depends(get_db)):
    phone = strip_phone_number(payload.phone_number)
    user = db.query(User).filter(User.phone_number == phone).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    token = issue_link_token(
        PURPOSE_VERIFY_AUREN, auren_user_id=str(user.id), phone_number=user.phone_number
    )
    plan = user.subscription.plan if user.subscription else None
    return AuthenticateResponse(verify_auren_token=token, display_name=user.display_name, plan=plan)


@router.post("/issue-assertion", response_model=IssueAssertionResponse)
def issue_assertion(current_user: User = Depends(get_current_user)):
    """For Flow B (bracelet-website initiates): the browser already has an
    Auren session here but no Gio one, so it can't get a verify_gio_token
    the normal way (that needs a Gio password). This mints the Auren-side
    equivalent — proof of the CURRENT session's identity, no password
    re-entry — for Flow A (gio-member-app initiates), where this browser's
    Auren session is exactly the proof braceletBackend's /confirm needs.
    """
    token = issue_link_token(PURPOSE_VERIFY_AUREN, auren_user_id=str(current_user.id))
    return IssueAssertionResponse(verify_auren_token=token)


@router.post("/confirm", response_model=ConfirmResponse)
def confirm(payload: ConfirmRequest, db: Session = Depends(get_db)):
    """Deliberately takes no session — see braceletBackend's /confirm for
    why: whichever frontend initiates, the browser is only ever logged
    into ONE of the two systems, so both confirm endpoints trust the two
    signed tokens instead of a current_user dependency. Either token may
    have come from /authenticate (password-verified) or /issue-assertion
    (session-verified) — confirm doesn't need to know or care which.
    """
    gio_claims = verify_link_token(payload.verify_gio_token, PURPOSE_VERIFY_GIO)
    auren_claims = verify_link_token(payload.verify_auren_token, PURPOSE_VERIFY_AUREN)
    bracelet_user_id = UUID(gio_claims["bracelet_user_id"])
    auren_user_id = UUID(auren_claims["auren_user_id"])

    user = db.get(User, auren_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auren account not found.")

    if user.linked_bracelet_user_id is not None:
        if user.linked_bracelet_user_id != bracelet_user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Auren account is already linked to a different Gio account.",
            )
        # Already linked to this exact pair — idempotent success, so a
        # retry after a partial failure on the Gio side doesn't error out.
    else:
        already_linked = db.query(User).filter(
            User.linked_bracelet_user_id == bracelet_user_id
        ).first()
        if already_linked:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Gio account is already linked to a different Auren account.",
            )
        user.linked_bracelet_user_id = bracelet_user_id
        user.linked_at = datetime.now(timezone.utc)
        db.commit()

    return ConfirmResponse(linked=True)


@router.post("/unlink", response_model=UnlinkResponse)
def unlink(payload: UnlinkRequest, db: Session = Depends(get_db)):
    """Flow C (admin-only, from bangle-bazi-admin) — takes no session, same
    token-trust design as /confirm. The token is minted by
    bracelet-management-backend only after its own RBAC check and only
    after it has already deleted its side of the link, so this endpoint's
    only job is clearing the Auren-side mirror of that same decision.
    """
    claims = verify_link_token(payload.admin_unlink_token, PURPOSE_ADMIN_UNLINK)
    auren_user_id = UUID(claims["auren_user_id"])

    user = db.get(User, auren_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auren account not found.")

    user.linked_bracelet_user_id = None
    user.linked_at = None
    db.commit()
    return UnlinkResponse(unlinked=True)


@router.post("/handoff", response_model=HandoffResponse)
def handoff(current_user: User = Depends(get_current_user)):
    """Cross-platform authenticated navigation (Auren -> Gio): mints a
    60-second, single-purpose token proving "this Auren session is linked
    to this Gio account" — braceletBackend's /account-link/sso-exchange
    trades it for a real Gio session.
    """
    if not current_user.linked_bracelet_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No linked Gio account.")

    token = issue_sso_token(PURPOSE_SSO_TO_GIO, bracelet_user_id=str(current_user.linked_bracelet_user_id))
    return HandoffResponse(sso_token=token)


@router.post("/sso-exchange", response_model=TokenResponse)
def sso_exchange(payload: SsoExchangeRequest, db: Session = Depends(get_db)):
    """Public, token-gated, no session required — the counterpart to
    braceletBackend's /account-link/handoff (Gio -> Auren direction).
    Trades a just-minted sso-to-auren token for a real Auren access +
    refresh token pair, exactly as /auth/login would issue one.
    """
    claims = verify_link_token(payload.sso_token, PURPOSE_SSO_TO_AUREN)
    auren_user_id = UUID(claims["auren_user_id"])

    user = db.get(User, auren_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auren account not found.")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/status", response_model=LinkStatusResponse)
def get_link_status(current_user: User = Depends(get_current_user)):
    if not current_user.linked_bracelet_user_id:
        return LinkStatusResponse(linked=False)
    return LinkStatusResponse(linked=True, bracelet_user_id=current_user.linked_bracelet_user_id)


@router.get("/admin/users", response_model=AdminUserListResponse)
def list_users_for_admin(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Read-only listing for bangle-bazi-admin's Auren Accounts page —
    plan/status/renews_at and the usage counters, live, every call. Gated
    by the shared service key rather than a user session since
    bangle-bazi-admin has no Auren session of its own to present (see
    AUREN_GIO_ACCOUNT_LINKING_PLAN.md §4d and §6 for the trade-off).
    """
    _require_service_key(request)

    query = db.query(User).outerjoin(Subscription, Subscription.user_id == User.id).order_by(User.created_at.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    items = [
        AdminUserListItem(
            auren_user_id=u.id,
            phone_number=u.phone_number,
            display_name=u.display_name,
            email=u.email,
            created_at=u.created_at,
            linked_bracelet_user_id=u.linked_bracelet_user_id,
            last_login_at=u.last_login_at,
            plan=u.subscription.plan if u.subscription else None,
            subscription_status=u.subscription.status if u.subscription else None,
            renews_at=u.subscription.renews_at if u.subscription else None,
            trial_ends_at=u.subscription.trial_ends_at if u.subscription else None,
            check_in_count_today=u.check_in_count_today,
            inner_reading_count_today=u.inner_reading_count_today,
        )
        for u in rows
    ]
    return AdminUserListResponse(items=items, total=total, page=page, page_size=page_size)
