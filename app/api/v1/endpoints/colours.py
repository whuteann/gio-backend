from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.schemas.colour import ColourOut
from app.services.content import COLOUR_ORDER, COLOURS

router = APIRouter(prefix="/colours", tags=["colours"])


@router.get("", response_model=list[ColourOut], dependencies=[Depends(get_current_user)])
def list_colours():
    return [ColourOut(**COLOURS[key]) for key in COLOUR_ORDER]


@router.get("/{key}", response_model=ColourOut, dependencies=[Depends(get_current_user)])
def get_colour(key: str):
    colour = COLOURS.get(key)
    if not colour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown colour.")
    return ColourOut(**colour)
