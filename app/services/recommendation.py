"""Recommendation generation.

Per spec: products are never stored in this DB — in the real system they'd
come from a third-party ecommerce API call, then an AI step would pick from
them using the user's inner state + Core Personality. Neither the API call
nor the AI step exist yet, so `_fetch_products_stub()` stands in for the
former and the existing focus->colour->tag matching (a direct port of
lib/recommendation.ts, not actually AI in the frontend either) stands in for
the latter. What *is* real: every inner reading (and check-in) snapshots its
own `RecommendationProfile` + `RecommendationItem` rows, so history is
genuinely preserved even though the selection logic is a placeholder.

Takes `focus_key` (app/services/scoring.py::resolve_focus_key's output)
rather than reading a focus label off the snapshot:
InnerStateSnapshot.current_focus is now the AI's own bilingual "ongoing
journey" phrasing (docs/behaviour_log_0006.md Phase 4), not this routing
key, so this function needs it passed in directly.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.recommendation import RecommendationItem, RecommendationProfile
from app.models.reflection import InnerStateSnapshot
from app.services.content import COLOURS, FOCUS_COPY, FOCUS_TO_COLOUR


def _fetch_products_stub() -> list[dict]:
    """Stand-in for the third-party ecommerce product API. Replace with a
    real HTTP call when that integration exists — everything downstream
    (tag matching, item building) already operates on this same shape."""
    return [
        {"id": "p_candle_amber", "title": "Amber Root Candle", "tags": ["energy", "lift"], "price": 68, "image_url": None},
        {"id": "p_oil_clarity", "title": "Clarity Roller Oil", "tags": ["clarity", "focus"], "price": 42, "image_url": None},
        {"id": "p_tea_calm", "title": "Quiet Hours Tea Blend", "tags": ["calm", "grounding"], "price": 28, "image_url": None},
        {"id": "p_journal_deep", "title": "Deep Focus Journal", "tags": ["clarity", "reflection"], "price": 36, "image_url": None},
        {"id": "p_bracelet_anchor", "title": "Anchor Bead Bracelet", "tags": ["grounding", "steadiness"], "price": 54, "image_url": None},
        {"id": "p_incense_spark", "title": "Bright Spark Incense", "tags": ["energy", "lift"], "price": 24, "image_url": None},
        {"id": "p_soak_release", "title": "Pressure Release Salt Soak", "tags": ["release", "calm"], "price": 32, "image_url": None},
    ]


def build_recommendation(
    db: Session,
    *,
    user_id: uuid.UUID,
    snapshot: InnerStateSnapshot,
    core_personality_id: uuid.UUID | None,
    focus_key: str,
    personality_title: str | None,
    trigger_type: str,
    trigger_check_in_session_id: uuid.UUID | None,
    trigger_inner_reading_id: uuid.UUID | None,
    is_premium: bool,
) -> RecommendationProfile:
    # Reuse the same static FOCUS_COPY content the old snapshot.summary
    # used to carry — this profile's own current_focus/summary are
    # deterministic bookkeeping, not the AI-generated Inner State fields.
    focus_copy = FOCUS_COPY[focus_key]
    focus_label = focus_copy["focus"]
    profile_data = FOCUS_TO_COLOUR.get(focus_label, FOCUS_TO_COLOUR["Sustaining balance"])
    colour = COLOURS[profile_data["colour_key"]]
    title_for_reason = personality_title or "you"

    profile = RecommendationProfile(
        id=uuid.uuid4(),
        user_id=user_id,
        state_snapshot_id=snapshot.id,
        core_personality_id=core_personality_id,
        trigger_type=trigger_type,
        trigger_check_in_session_id=trigger_check_in_session_id,
        trigger_inner_reading_id=trigger_inner_reading_id,
        current_focus=focus_label,
        summary=focus_copy["summary"],
        colour_key=colour["key"],
        status="READY",
        generated_at=datetime.now(timezone.utc),
    )
    db.add(profile)
    db.flush()

    profile.items.append(RecommendationItem(
        type="COLOUR", reference_id=colour["key"],
        title=colour["name"], reason=f"Matched to your current focus — {focus_label.lower()}.", rank=1,
    ))
    profile.items.append(RecommendationItem(
        type="ROUTINE", reference_id=None,
        title=profile_data["routine"], reason=f"A small, doable step suited to {title_for_reason.lower()}.", rank=2,
    ))

    matched = [p for p in _fetch_products_stub() if set(p["tags"]) & set(profile_data["tags"])]
    limit = 3 if is_premium else 1
    for i, product in enumerate(matched[:limit]):
        profile.items.append(RecommendationItem(
            type="PRODUCT", reference_id=product["id"],
            title=product["title"],
            reason=(f"Chosen from your recent history and current {focus_label.lower()} — pairs with {colour['name'].lower()}."
                    if is_premium else f"A simple match for {focus_label.lower()}."),
            rank=3 + i, image_url=product["image_url"], price=product["price"], destination_url=None,
        ))

    db.flush()
    return profile
