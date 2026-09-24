from pydantic import BaseModel


class StreakOut(BaseModel):
    current: int
    best: int
    last_reflection_date: str | None
    milestones_awarded: list[int]


class GardenOut(BaseModel):
    week_start: str
    stage: int
    actions_this_week: int


class BadgeOut(BaseModel):
    key: str
    group: str
    title: str
    description: str
    icon: str
    earned: bool
    earned_at: str | None


class ProgressOut(BaseModel):
    xp_total: int
    streak: StreakOut
    garden: GardenOut
    quests_today: list[str]
    badges: list[BadgeOut]


class RewardOut(BaseModel):
    key: str
    title: str
    description: str
    icon: str
    requirement: str
    state: str
    unlocked_at: str | None
    redeemed_at: str | None
