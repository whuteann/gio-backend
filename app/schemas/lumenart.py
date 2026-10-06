from pydantic import BaseModel


class LumenartProductOut(BaseModel):
    id: str
    handle: str
    name: str
    image_url: str | None
    price: float | None
    currency: str
    destination_url: str | None
