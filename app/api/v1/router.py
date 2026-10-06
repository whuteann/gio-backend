from fastapi import APIRouter

from app.api.v1.endpoints import (
    account_link,
    auth,
    checkins,
    colours,
    core_personality,
    journal,
    me,
    onboarding,
    personality,
    progress,
    readings,
    recommendations,
    rewards,
    snapshots,
    subscription,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(onboarding.router)
api_router.include_router(personality.router)
api_router.include_router(core_personality.router)
api_router.include_router(checkins.router)
api_router.include_router(readings.router)
api_router.include_router(snapshots.router)
api_router.include_router(recommendations.router)
api_router.include_router(progress.router)
api_router.include_router(rewards.router)
api_router.include_router(journal.router)
api_router.include_router(subscription.router)
api_router.include_router(colours.router)
api_router.include_router(account_link.router)
