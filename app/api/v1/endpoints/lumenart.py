from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.schemas.lumenart import LumenartProductOut
from app.services.lumenart import get_phone_case_candidates

router = APIRouter(prefix="/lumenart", tags=["lumenart"])


@router.get("/products", response_model=list[LumenartProductOut], dependencies=[Depends(get_current_user)])
def list_lumenart_products(db: Session = Depends(get_db)):
    """Inspection endpoint — the exact same lazy, 24h-cached LumenArt
    catalog the recommendation engine draws its phone case pick from (see
    app/services/lumenart.py). Not called by the member app's own UI;
    LumenArt products are otherwise only ever shown inside a
    recommendation's phone case card, never browsed as their own catalog
    (see docs/recommendation_engine.md)."""
    candidates = get_phone_case_candidates(db)
    db.commit()
    return [
        LumenartProductOut(
            id=c["id"],
            handle=c["handle"],
            name=c["name"],
            image_url=c.get("primary_image"),
            price=float(c["price"]) if c.get("price") is not None else None,
            currency=c.get("currency") or "MYR",
            destination_url=f"https://lumenart.store/products/{c['handle']}" if c.get("handle") else None,
        )
        for c in candidates
    ]
