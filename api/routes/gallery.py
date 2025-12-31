from fastapi import APIRouter, HTTPException
from database.mongo import gallery
from database.schemas.gallery import GalleryResponse
from typing import List

router = APIRouter(prefix="/gallery", tags=["Gallery"])


@router.get("", response_model=List[GalleryResponse])
def get_all_galleries(limit: int = 50):
    docs = list(gallery.find({}).sort("year", 1).limit(limit))
    items = []
    for d in docs:
        items.append(
            {
                "id": str(d.get("_id")),
                "year": d.get("year"),
                "images": d.get("images") or [],
                "modifiedBy": d.get("modifiedBy"),
                "createdAt": d.get("createdAt"),
                "updatedAt": d.get("updatedAt"),
            }
        )
    return items


@router.get("/{year}", response_model=GalleryResponse)
def get_gallery_by_year(year: int):
    d = gallery.find_one({"year": year})
    if not d:
        raise HTTPException(status_code=404, detail="Year not found")
    return {
        "id": str(d.get("_id")),
        "year": d.get("year"),
        "images": d.get("images") or [],
        "modifiedBy": d.get("modifiedBy"),
        "createdAt": d.get("createdAt"),
        "updatedAt": d.get("updatedAt"),
    }
