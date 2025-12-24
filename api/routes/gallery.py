from fastapi import APIRouter, HTTPException
from database.mongo import gallery_collection
from database.schemas.gallery import Gallery

router = APIRouter(prefix="/gallery", tags=["Gallery"])


@router.get("", response_model=list[Gallery])
def get_all_galleries(limit: int = 50):
    data = list(gallery_collection.find({}, {"_id": 0}).sort("year", 1).limit(limit))
    return data


@router.get("/{year}", response_model=Gallery)
def get_gallery_by_year(year: int):
    data = gallery_collection.find_one(
        {"year": year},
        {"_id": 0}
    )

    if not data:
        raise HTTPException(status_code=404, detail="Year not found")

    return data
