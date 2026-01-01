from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, HTTPException
from database.mongo import gallery
from database.schemas.gallery import GalleryResponse

router = APIRouter(prefix="/gallery", tags=["Gallery"])


def _normalize_images(raw: Any) -> list[dict]:
    if not raw:
        return []
    items: list[dict] = []
    for img in raw:
        if isinstance(img, str):
            items.append({"url": img, "caption": "", "location": "", "verified": False})
            continue
        if isinstance(img, dict):
            url = img.get("url") or img.get("secure_url") or img.get("src")
            if isinstance(url, str) and url:
                items.append(
                    {
                        "url": url,
                        "caption": img.get("caption") or "",
                        "location": img.get("location") or "",
                        "verified": bool(img.get("verified")) if "verified" in img else False,
                    }
                )
    return items


@router.get("", response_model=List[GalleryResponse])
def get_all_galleries(limit: int = 50):
    docs = list(gallery.find({}).sort("year", 1).limit(limit))
    items = []
    for d in docs:
        items.append(
            {
                "id": str(d.get("_id")),
                "year": d.get("year"),
                "images": _normalize_images(d.get("images")),
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
        "images": _normalize_images(d.get("images")),
        "modifiedBy": d.get("modifiedBy"),
        "createdAt": d.get("createdAt"),
        "updatedAt": d.get("updatedAt"),
    }
