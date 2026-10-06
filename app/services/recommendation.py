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
one (docs/behaviour_log_0012.md, decision 4): at most one live product
fetch + AI pick happens per user per UTC day. A user's first
check-in/reading of a new day creates a fresh profile and runs the full
pipeline; any later submission that same day updates the same profile's
COLOUR/ROUTINE items (cheap, deterministic — might as well reflect the
latest focus) but leaves its PRODUCT items untouched, carried forward
rather than re-fetched/re-picked. This relies on the caller having already
serialized concurrent requests for this user via
`app/services/narrative.py::lock_user` before reaching here — see
checkins.py/readings.py, which call it up front — so the
`(user_id, recommendation_date)` unique constraint is never raced.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationItem, RecommendationProfile
from app.models.reflection import InnerStateSnapshot
from app.models.user import User
from app.services.ai_recommendation import generate_recommendation
from app.services.content import COLOURS, FOCUS_COPY, FOCUS_TO_COLOUR, FOCUS_TO_MATERIAL
from app.services.gamification import today_utc
from app.services.narrative_prompt import build_narrative_prompt
from app.services.phonecase_api import fetch_phone_cases
from app.services.product_api import fetch_products, parse_specifications

logger = logging.getLogger(__name__)


def _parse_price(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


async def _fetch_and_pick(*, colour_key: str, material_affinity: str, focus_label: str, narrative_prompt: str, limit: int) -> dict:
    stone_candidates, phone_case_candidates = await asyncio.gather(
        fetch_products(colour_key, stone_type=material_affinity),
        fetch_phone_cases(),
    )
    return await generate_recommendation(
        narrative_prompt=narrative_prompt, focus_label=focus_label, material_affinity=material_affinity,
        stone_candidates=stone_candidates, phone_case_candidates=phone_case_candidates, limit=limit,
    )


def _product_item(product: dict, *, rank: int) -> RecommendationItem:
    product_id = product.get("id")
    return RecommendationItem(
        type="PRODUCT", reference_id=str(product_id) if product_id else None,
        title=product.get("name") or "Recommended piece", title_zh=product.get("name"),
        reason=product["reason_en"], reason_zh=product["reason_zh"],
        rank=rank,
        image_url=product.get("primary_image"),
        price=_parse_price(product.get("price")),
        currency=product.get("currency") or "MYR",
        destination_url=f"https://www.giobyquartzic.com/products/{product_id}" if product_id else None,
        material_tag=product.get("material_tag"),
        specifications=parse_specifications(product.get("specifications")) or None,
    )


def _phone_case_item(product: dict, *, rank: int) -> RecommendationItem:
    product_id = product.get("id")
    return RecommendationItem(
        type="PHONE_CASE", reference_id=str(product_id) if product_id else None,
        title=product.get("name") or "Recommended piece", title_zh=product.get("name"),
        reason=product["reason_en"], reason_zh=product["reason_zh"],
        rank=rank,
        image_url=product.get("primary_image"),
        price=_parse_price(product.get("price")),
        currency=product.get("currency") or "MYR",
        destination_url=f"https://www.giobyquartzic.com/products/{product_id}" if product_id else None,
        specifications=parse_specifications(product.get("specifications")) or None,
    )


def _refresh_product_items(
    profile: RecommendationProfile, *, colour_key: str, material_affinity: str, focus_label: str,
    narrative_prompt: str, limit: int, next_rank: int,
) -> None:
    """Best-effort: any failure here (vendor API down, AI call failing)
    leaves the profile with no PRODUCT/PHONE_CASE items and no letter
    rather than failing the submission that triggered it — see module
    docstring."""
    try:
        result = asyncio.run(_fetch_and_pick(
            colour_key=colour_key, material_affinity=material_affinity, focus_label=focus_label,
            narrative_prompt=narrative_prompt, limit=limit,
        ))
    except Exception:
        logger.exception(
            "Recommendation fetch/pick failed for recommendation %s (colour=%s, material=%s) — no PRODUCT/PHONE_CASE items this run.",
            profile.id, colour_key, material_affinity,
        )
        result = {"letter_en": "", "letter_zh": "", "feature": None, "others": [], "phone_case": []}

    profile.letter_en = result["letter_en"] or None
    profile.letter_zh = result["letter_zh"] or None

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
    is_premium: bool,
) -> RecommendationProfile:
    focus_copy = FOCUS_COPY[focus_key]
    focus_label = focus_copy["focus"]
    profile_data = FOCUS_TO_COLOUR.get(focus_label, FOCUS_TO_COLOUR["Sustaining balance"])
    colour = COLOURS[profile_data["colour_key"]]
    material_affinity = FOCUS_TO_MATERIAL.get(focus_label, FOCUS_TO_MATERIAL["Sustaining balance"])
    title_for_reason = personality_title or "you"
    today = today_utc()
    limit = 3 if is_premium else 1

    existing = db.query(RecommendationProfile).filter_by(user_id=user.id, recommendation_date=today).first()

    if existing is not None:
        existing.state_snapshot_id = snapshot.id
        existing.core_personality_id = core_personality_id
        existing.trigger_type = trigger_type
        existing.trigger_check_in_session_id = trigger_check_in_session_id
        existing.trigger_inner_reading_id = trigger_inner_reading_id
        existing.current_focus = focus_label
        existing.current_focus_zh = focus_copy["focus_zh"]
        existing.summary = focus_copy["summary"]
        existing.summary_zh = focus_copy["summary_zh"]
        existing.colour_key = colour["key"]
        existing.material_affinity = material_affinity
        existing.generated_at = datetime.now(timezone.utc)
        for item in [i for i in existing.items if i.type in ("COLOUR", "ROUTINE")]:
            existing.items.remove(item)
            db.delete(item)
        db.flush()
        existing.items.append(RecommendationItem(
            type="COLOUR", reference_id=colour["key"],
            title=colour["name"], title_zh=colour["name_zh"],
            reason=f"Matched to your current focus — {focus_label.lower()}.",
            reason_zh=f"根据你当前的重点——{focus_copy['focus_zh']}——为你匹配。",
            rank=1,
        ))
        existing.items.append(RecommendationItem(
            type="ROUTINE", reference_id=None,
            title=profile_data["routine"], title_zh=profile_data["routine_zh"],
            reason=f"A small, doable step suited to {title_for_reason.lower()}.",
            reason_zh="一个适合你此刻状态的小小可行步骤。",
            rank=2,
        ))
        db.flush()

        # Only genuinely skip the product step if it already succeeded once
        # today — an earlier failed attempt (vendor API down, AI hiccup)
        # must not permanently strand the user with zero products for the
        # rest of the day just because *a* profile row exists for today.
        if not any(i.type == "PRODUCT" for i in existing.items):
            narrative_prompt = build_narrative_prompt(db, user, snapshot=snapshot, focus_label=focus_label, colour=colour)
            _refresh_product_items(
                existing, colour_key=colour["key"], material_affinity=material_affinity, focus_label=focus_label,
                narrative_prompt=narrative_prompt, limit=limit, next_rank=3,
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
        summary=focus_copy["summary"],
        summary_zh=focus_copy["summary_zh"],
        colour_key=colour["key"],
        material_affinity=material_affinity,
        status="READY",
        generated_at=datetime.now(timezone.utc),
    )
    db.add(profile)
    db.flush()

    profile.items.append(RecommendationItem(
        type="COLOUR", reference_id=colour["key"],
        title=colour["name"], title_zh=colour["name_zh"],
        reason=f"Matched to your current focus — {focus_label.lower()}.",
        reason_zh=f"根据你当前的重点——{focus_copy['focus_zh']}——为你匹配。",
        rank=1,
    ))
    profile.items.append(RecommendationItem(
        type="ROUTINE", reference_id=None,
        title=profile_data["routine"], title_zh=profile_data["routine_zh"],
        reason=f"A small, doable step suited to {title_for_reason.lower()}.",
        reason_zh="一个适合你此刻状态的小小可行步骤。",
        rank=2,
    ))
    db.flush()

    narrative_prompt = build_narrative_prompt(db, user, snapshot=snapshot, focus_label=focus_label, colour=colour)
    _refresh_product_items(
        profile, colour_key=colour["key"], material_affinity=material_affinity, focus_label=focus_label,
        narrative_prompt=narrative_prompt, limit=limit, next_rank=3,
    )

    db.flush()
    return profile
