"""Recommendation generation. See docs/behaviour_log_0012.md.

Products now come from a real third-party ecommerce API
(app/services/product_api.py), colour-filtered on the unified recommended
colour (this same function's own `colour_key` — the single source of
truth for product-matching purposes), with an AI step
(app/services/ai_recommendation.py) picking which of the filtered
candidates to actually recommend, grounded on a narrative prompt
(app/services/narrative_prompt.py) assembled from the user's inner state,
recent reflections, and journaling. COLOUR/ROUTINE items stay the
deterministic focus->colour matching this always used (a direct port of
lib/recommendation.ts, not AI either).

`RecommendationProfile` is now a **daily** artifact, not a per-submission
one (docs/behaviour_log_0012.md, decision 4): at most one successful stone-product
fetch + AI pick happens per user per UTC day. A user's first
check-in/reading of a new day creates a fresh profile and runs the full
pipeline; any later submission that same day updates the same profile's
COLOUR/ROUTINE items (cheap, deterministic — might as well reflect the
latest focus) but leaves its PRODUCT items untouched, carried forward
rather than re-fetched/re-picked. Phone cases now follow the latest displayed
colour even within the day; see docs/phone_case_colour_matching.md.
This relies on the caller having already
serialized concurrent requests for this user via
`app/services/narrative.py::lock_user` before reaching here — see
checkins.py/readings.py, which call it up front — so the
`(user_id, recommendation_date)` unique constraint is never raced.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.database import SessionLocal

from app.models.recommendation import RecommendationItem, RecommendationProfile
from app.models.reflection import InnerStateSnapshot
from app.models.user import User
from app.services.ai_recommendation import generate_recommendation, generate_phone_case_recommendation
from app.services.content import COLOURS, FOCUS_COPY, FOCUS_TO_COLOUR, FOCUS_TO_MATERIAL, STONE_TYPES
from app.services.gamification import today_utc
from app.services.lumenart import get_phone_case_candidates
from app.services.phone_case_colours import matching_cases
from app.services.narrative import lock_user
from app.services.narrative_prompt import build_narrative_prompt
from app.services import languages
from app.services.product_api import fetch_products, parse_specifications
from app.services.scoring import resolve_focus_key

logger = logging.getLogger(__name__)


def _parse_price(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


async def _fetch_and_pick(
    *, db: Session, colour_key: str, material_affinity: str, focus_label: str, narrative_prompt: str,
    include_phone_cases: bool = True,
) -> dict:
    # Phone case candidates come from a sync, DB-backed lazy cache (see
    # lumenart.py) rather than a live vendor call, so there's nothing to
    # actually gather concurrently with the stone fetch here. All 3 stone
    # types are fetched (same colour, different `type=`) so the product
    # set can carry one pick per type rather than 3 from whichever single
    # type the focus happened to match.
    phone_case_candidates = matching_cases(get_phone_case_candidates(db), colour_key) if include_phone_cases else []
    type_results = await asyncio.gather(*(fetch_products(colour_key, stone_type=t) for t in STONE_TYPES))
    stone_candidates_by_type = dict(zip(STONE_TYPES, type_results))
    return await generate_recommendation(
        narrative_prompt=narrative_prompt, focus_label=focus_label, material_affinity=material_affinity,
        stone_candidates_by_type=stone_candidates_by_type, phone_case_candidates=phone_case_candidates,
        colour_key=colour_key,
    )


def _colour_item(colour: dict, focus_copy: dict, focus_label: str) -> RecommendationItem:
    """The deterministic COLOUR row. Extracted because it was written out
    twice — once per branch of ensure_recommendation — which is two places
    to forget a language in."""
    return RecommendationItem(
        type="COLOUR", reference_id=colour["key"],
        title=colour["name"], title_zh=colour["name_zh"], title_ms=colour["name_ms"],
        reason=f"Matched to your current focus — {focus_label.lower()}.",
        reason_zh=f"根据你当前的重点——{focus_copy['focus_zh']}——为你匹配。",
        reason_ms=f"Dipadankan dengan fokus anda sekarang — {focus_copy['focus_ms'].lower()}.",
        rank=1,
    )


def _routine_item(profile_data: dict, title_for_reason: str) -> RecommendationItem:
    """The deterministic ROUTINE row — see _colour_item on why it's here."""
    return RecommendationItem(
        type="ROUTINE", reference_id=None,
        title=profile_data["routine"], title_zh=profile_data["routine_zh"],
        title_ms=profile_data["routine_ms"],
        reason=f"A small, doable step suited to {title_for_reason.lower()}.",
        # zh/ms drop the state label the English line interpolates: it reads
        # naturally in English and awkwardly when inflected into either of
        # the others, and the label is already on screen above this row.
        reason_zh="一个适合你此刻状态的小小可行步骤。",
        reason_ms="Satu langkah kecil yang mudah dilakukan, sesuai dengan keadaan anda kini.",
        rank=2,
    )


def _product_item(product: dict, *, rank: int) -> RecommendationItem:
    product_id = product.get("id")
    return RecommendationItem(
        type="PRODUCT", reference_id=str(product_id) if product_id else None,
        # The vendor supplies one product name, not a per-language set — the
        # same string in every column, deliberately, so a Malay reader sees
        # the real product name rather than a blank.
        title=product.get("name") or "Recommended piece",
        title_zh=product.get("name"), title_ms=product.get("name"),
        reason=product["reason_en"], reason_zh=product["reason_zh"],
        reason_ms=product.get("reason_ms"),
        rank=rank,
        image_url=product.get("primary_image"),
        price=_parse_price(product.get("price")),
        currency=product.get("currency") or "MYR",
        destination_url=f"https://www.giobyquartzic.com/products/{product_id}" if product_id else None,
        material_tag=product.get("material_tag"),
        category=product.get("stone_type"),
        specifications=parse_specifications(product.get("specifications")) or None,
    )


def _phone_case_item(product: dict, *, rank: int) -> RecommendationItem:
    product_id = product.get("id")
    handle = product.get("handle")
    return RecommendationItem(
        type="PHONE_CASE", reference_id=str(product_id) if product_id else None,
        # The vendor supplies one product name, not a per-language set — the
        # same string in every column, deliberately, so a Malay reader sees
        # the real product name rather than a blank.
        title=product.get("name") or "Recommended piece",
        title_zh=product.get("name"), title_ms=product.get("name"),
        reason=product["reason_en"], reason_zh=product["reason_zh"],
        reason_ms=product.get("reason_ms"),
        rank=rank,
        image_url=product.get("primary_image"),
        price=_parse_price(product.get("price")),
        currency=product.get("currency") or "MYR",
        # LumenArt is a separate vendor/storefront from the stone catalog
        # above — its own domain, keyed by Shopify's product handle, not
        # the giobyquartzic.com product id path the stone picks use.
        destination_url=f"https://lumenart.store/products/{handle}" if handle else None,
        specifications=parse_specifications(product.get("specifications")) or None,
    )


def _refresh_product_items(
    profile: RecommendationProfile, *, db: Session, colour_key: str, material_affinity: str, focus_label: str,
    narrative_prompt: str, next_rank: int,
    include_phone_cases: bool = True,
) -> None:
    """Best-effort: any failure here (vendor API down, AI call failing)
    leaves the profile with no PRODUCT/PHONE_CASE items and no letter
    rather than failing the submission that triggered it — see module
    docstring."""
    try:
        result = asyncio.run(_fetch_and_pick(
            db=db, colour_key=colour_key, material_affinity=material_affinity, focus_label=focus_label,
            narrative_prompt=narrative_prompt,
            include_phone_cases=include_phone_cases,
        ))
    except Exception:
        logger.exception(
            "Recommendation fetch/pick failed for recommendation %s (colour=%s, material=%s) — no PRODUCT/PHONE_CASE items this run.",
            profile.id, colour_key, material_affinity,
        )
        result = {**{f"letter_{code}": "" for code in languages.SUPPORTED},
                  "feature": None, "others": [], "phone_case": []}

    # Retrying missing stone picks must not append duplicate phone cases.
    replace_types = ("PRODUCT", "PHONE_CASE") if include_phone_cases else ("PRODUCT",)
    for item in [i for i in profile.items if i.type in replace_types]:
        profile.items.remove(item)
        db.delete(item)
    for code in languages.SUPPORTED:
        setattr(profile, f"letter_{code}", result.get(f"letter_{code}") or None)

    rank = next_rank
    if result["feature"]:
        profile.items.append(_product_item(result["feature"], rank=rank))
        rank += 1
    for product in result["others"]:
        profile.items.append(_product_item(product, rank=rank))
        rank += 1
    for product in result["phone_case"]:
        profile.items.append(_phone_case_item(product, rank=rank))
        rank += 1
    if include_phone_cases:
        _record_case_selection(profile, db=db, colour_key=colour_key, succeeded=bool(result["phone_case"]))
    else:
        # Stones can recover on a later load without moving/duplicating cases.
        for item in [i for i in profile.items if i.type == "PHONE_CASE"]:
            item.rank = rank
            rank += 1


def _record_case_selection(profile: RecommendationProfile, *, db: Session, colour_key: str, succeeded: bool) -> None:
    from app.models.lumenart import LumenartProduct
    # Read the cache only: don't repeat a failed upstream refresh in one request.
    rows = db.query(LumenartProduct).all()
    has_match = any(colour_key in (r.colour_keys or []) for r in rows)
    known_catalogue = bool(rows) and all(r.colour_keys is not None for r in rows)
    profile.phone_case_colour_key = colour_key
    profile.phone_case_checked_at = datetime.now(timezone.utc)
    profile.phone_case_status = "READY" if succeeded else ("NO_MATCH" if known_catalogue and not has_match else "UNAVAILABLE")


def _sync_phone_case_items(profile: RecommendationProfile, *, db: Session, colour_key: str,
                          narrative_prompt_factory) -> None:
    """Keep cases aligned with the current colour without replacing daily stones.

    Also upgrades legacy picks. Successful same-colour picks stay stable. Missing
    matches / model failures retry after 10 minutes, not on every page load.
    Catalogue refreshes can remove a previously eligible design immediately.
    """
    all_candidates = get_phone_case_candidates(db)
    candidates = matching_cases(all_candidates, colour_key)
    allowed_ids = {str(c["id"]) for c in candidates}
    removed = False
    for item in [i for i in profile.items if i.type == "PHONE_CASE" and i.reference_id not in allowed_ids]:
        profile.items.remove(item)
        db.delete(item)
        removed = True
    current = [i for i in profile.items if i.type == "PHONE_CASE"]
    now = datetime.now(timezone.utc)
    if profile.phone_case_colour_key == colour_key and not removed:
        if current and profile.phone_case_status == "READY":
            return
        if profile.phone_case_checked_at and now - profile.phone_case_checked_at < timedelta(minutes=10):
            return
    if not candidates:
        _record_case_selection(profile, db=db, colour_key=colour_key, succeeded=False)
        return
    try:
        picks = asyncio.run(generate_phone_case_recommendation(
            narrative_prompt=narrative_prompt_factory(), colour_key=colour_key, phone_case_candidates=candidates))
    except Exception:
        logger.exception("Colour-matched phone case selection failed for profile %s", profile.id)
        _record_case_selection(profile, db=db, colour_key=colour_key, succeeded=False)
        return
    for item in current:
        profile.items.remove(item)
        db.delete(item)
    rank = max((i.rank for i in profile.items), default=2) + 1
    for product in picks:
        if str(product.get("id")) in allowed_ids:
            profile.items.append(_phone_case_item(product, rank=rank))
            rank += 1
    _record_case_selection(profile, db=db, colour_key=colour_key,
                           succeeded=any(i.type == "PHONE_CASE" for i in profile.items))


def build_recommendation(
    db: Session,
    *,
    user: User,
    snapshot: InnerStateSnapshot,
    core_personality_id: uuid.UUID | None,
    focus_key: str,
    personality_title: str | None,
    trigger_type: str,
    trigger_check_in_session_id: uuid.UUID | None,
    trigger_inner_reading_id: uuid.UUID | None,
) -> RecommendationProfile:
    focus_copy = FOCUS_COPY[focus_key]
    focus_label = focus_copy["focus"]
    profile_data = FOCUS_TO_COLOUR.get(focus_label, FOCUS_TO_COLOUR["Sustaining balance"])
    colour = COLOURS[profile_data["colour_key"]]
    material_affinity = FOCUS_TO_MATERIAL.get(focus_label, FOCUS_TO_MATERIAL["Sustaining balance"])
    title_for_reason = personality_title or "you"
    today = today_utc()

    existing = db.query(RecommendationProfile).filter_by(user_id=user.id, recommendation_date=today).first()

    if existing is not None:
        existing.state_snapshot_id = snapshot.id
        existing.core_personality_id = core_personality_id
        existing.trigger_type = trigger_type
        existing.trigger_check_in_session_id = trigger_check_in_session_id
        existing.trigger_inner_reading_id = trigger_inner_reading_id
        existing.current_focus = focus_label
        existing.current_focus_zh = focus_copy["focus_zh"]
        existing.current_focus_ms = focus_copy["focus_ms"]
        existing.summary = focus_copy["summary"]
        existing.summary_zh = focus_copy["summary_zh"]
        existing.summary_ms = focus_copy["summary_ms"]
        existing.colour_key = colour["key"]
        existing.material_affinity = material_affinity
        existing.generated_at = datetime.now(timezone.utc)
        for item in [i for i in existing.items if i.type in ("COLOUR", "ROUTINE")]:
            existing.items.remove(item)
            db.delete(item)
        db.flush()
        existing.items.append(_colour_item(colour, focus_copy, focus_label))
        existing.items.append(_routine_item(profile_data, title_for_reason))
        db.flush()

        # Only genuinely skip the product step if it already succeeded once
        # today — an earlier failed attempt (vendor API down, AI hiccup)
        # must not permanently strand the user with zero products for the
        # rest of the day just because *a* profile row exists for today.
        if not any(i.type == "PRODUCT" for i in existing.items):
            narrative_prompt = build_narrative_prompt(db, user, snapshot=snapshot, focus_label=focus_label, colour=colour)
            _refresh_product_items(
                existing, db=db, colour_key=colour["key"], material_affinity=material_affinity, focus_label=focus_label,
                narrative_prompt=narrative_prompt, next_rank=3,
                include_phone_cases=False,
            )
            db.flush()
        _sync_phone_case_items(
            existing, db=db, colour_key=colour["key"],
            narrative_prompt_factory=lambda: build_narrative_prompt(
                db, user, snapshot=snapshot, focus_label=focus_label, colour=colour),
        )
        db.flush()
        return existing

    profile = RecommendationProfile(
        id=uuid.uuid4(),
        user_id=user.id,
        state_snapshot_id=snapshot.id,
        core_personality_id=core_personality_id,
        trigger_type=trigger_type,
        trigger_check_in_session_id=trigger_check_in_session_id,
        trigger_inner_reading_id=trigger_inner_reading_id,
        recommendation_date=today,
        current_focus=focus_label,
        current_focus_zh=focus_copy["focus_zh"],
        current_focus_ms=focus_copy["focus_ms"],
        summary=focus_copy["summary"],
        summary_zh=focus_copy["summary_zh"],
        summary_ms=focus_copy["summary_ms"],
        colour_key=colour["key"],
        material_affinity=material_affinity,
        status="READY",
        generated_at=datetime.now(timezone.utc),
    )
    db.add(profile)
    db.flush()

    profile.items.append(_colour_item(colour, focus_copy, focus_label))
    profile.items.append(_routine_item(profile_data, title_for_reason))
    db.flush()

    narrative_prompt = build_narrative_prompt(db, user, snapshot=snapshot, focus_label=focus_label, colour=colour)
    _refresh_product_items(
        profile, db=db, colour_key=colour["key"], material_affinity=material_affinity, focus_label=focus_label,
        narrative_prompt=narrative_prompt, next_rank=3,
    )

    db.flush()
    return profile


def ensure_recommendation(db: Session, user: User) -> RecommendationProfile | None:
    """Today's recommendation for `user`, generating one if there isn't one.

    The second way a profile comes into being. The first is a check-in or
    reading submission (cascade.py); this one covers everybody who simply
    opens the app — including accounts whose only reflections predate the
    feature, who otherwise would never get a recommendation at all.

    Returns None only when there is genuinely nothing to build from: no
    InnerStateSnapshot has ever been written for this user, which means they
    have never completed a check-in or reading. That is the sole empty case.

    Cheap when today's profile already exists — build_recommendation finds it
    by `(user_id, recommendation_date)` and refreshes only the deterministic
    COLOUR/ROUTINE items, re-running the product fetch solely if an earlier
    attempt today left none.
    """
    snapshot = (
        db.query(InnerStateSnapshot)
        .filter_by(user_id=user.id)
        .order_by(InnerStateSnapshot.created_at.desc())
        .first()
    )
    if snapshot is None:
        return None

    # build_recommendation's docstring requires the caller to have serialized
    # this user first — without it, a page load racing the login warm-up
    # violates the (user_id, recommendation_date) unique constraint.
    lock_user(db, user)

    dims = {
        "emotional_energy": snapshot.emotional_energy,
        "mental_clarity": snapshot.mental_clarity,
        "inner_pressure": snapshot.inner_pressure,
        "grounding": snapshot.grounding,
    }
    return build_recommendation(
        db,
        user=user,
        snapshot=snapshot,
        core_personality_id=user.core_personality.id if user.core_personality else None,
        focus_key=resolve_focus_key(dims),
        personality_title=user.core_personality.title_en if user.core_personality else None,
        # The trigger is carried forward from the snapshot rather than left
        # null: ck_recommendation_single_trigger requires exactly one, and
        # naming the reflection this state actually came from is truer than
        # inventing a "page load" trigger type.
        trigger_type=snapshot.source_type,
        trigger_check_in_session_id=snapshot.check_in_session_id,
        trigger_inner_reading_id=snapshot.inner_reading_id,
    )


def warm_recommendation(user_id) -> None:
    """Fire-and-forget cache warm for background tasks (login/refresh).

    Owns its own session — the request's is closed by the time a
    BackgroundTask runs. Never raises: a failed warm just means the page
    generates on load instead, which is the behaviour without this.
    """
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is None:
            return
        if ensure_recommendation(db, user) is not None:
            db.commit()
            logger.info("Recommendation warmed for user=%s.", user_id)
        else:
            db.rollback()
    except Exception:
        logger.exception("Recommendation warm failed for user=%s.", user_id)
        db.rollback()
    finally:
        db.close()
