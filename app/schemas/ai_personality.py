from pydantic import BaseModel

from app.schemas.common import NumberPoint


class CorePersonalityGeneration(BaseModel):
    """The text_format schema handed to client.responses.parse — single
    language per call (see app/services/ai_personality.py). Every field
    here maps 1:1 to a bilingual column pair on CorePersonality."""

    title: str
    subtitle: str
    overview: str
    birthday_number_points: list[NumberPoint]
    life_path_number_points: list[NumberPoint]
    talent_number_points: list[NumberPoint]
    summary: str
