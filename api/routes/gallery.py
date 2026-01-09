from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, HTTPException
from database.mongo import gallery
from database.schemas.gallery import GalleryResponse

router = APIRouter(prefix="/gallery", tags=["Gallery"])


def _normalize_images(raw: Any, parent_year: int | None = None) -> list[dict]:
    if not raw:
        return []
    items: list[dict] = []
    for img in raw:
        if isinstance(img, str):
            items.append(
                {
                    "url": img,
                    "publicId": None,
                    "year": parent_year,
                    "caption": "",
                    "location": "",
                    "verified": False,
                }
            )
            continue
        if isinstance(img, dict):
            url = img.get("url") or img.get("secure_url") or img.get("src")
            if isinstance(url, str) and url:
                public_id = img.get("publicId") or img.get("public_id")
                if not isinstance(public_id, str) or not public_id:
                    public_id = None

                caption = img.get("caption") if "caption" in img else ""
                if caption is not None and not isinstance(caption, str):
                    caption = ""

                location = img.get("location") if "location" in img else ""
                if location is not None and not isinstance(location, str):
                    location = ""

                image_year = img.get("year") if "year" in img else parent_year
                if image_year is not None and not isinstance(image_year, int):
                    image_year = parent_year

                items.append(
                    {
                        "url": url,
                        "publicId": public_id,
                        "year": image_year,
                        "caption": caption,
                        "location": location,
                        "verified": bool(img.get("verified")) if "verified" in img else False,
                    }
                )
    return items


@router.get("", response_model=List[GalleryResponse])
def get_all_galleries(limit: int = 50):
    docs = list(gallery.find({}).sort("year", 1).limit(limit))
    items = []
    for d in docs:
        year = d.get("year")
        items.append(
            {
                "id": str(d.get("_id")),
                "year": year,
                "images": _normalize_images(d.get("images"), parent_year=year),
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
        "images": _normalize_images(d.get("images"), parent_year=year),
        "modifiedBy": d.get("modifiedBy"),
        "createdAt": d.get("createdAt"),
        "updatedAt": d.get("updatedAt"),
    }
