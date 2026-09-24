from pydantic import BaseModel


class ColourOut(BaseModel):
    key: str
    name: str
    swatch: str
    traits: list[str]
    description: str
    article: str
    benefit: str
    affirmations: list[str]
    positive_traits: list[str]
    negative_traits: list[str]
