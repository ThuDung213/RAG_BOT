from __future__ import annotations

from fastapi import APIRouter

from database.mongo import locations
from database.schemas.locations import LocationResponse

router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get("", response_model=list[LocationResponse])
def get_locations_public():
    data = list(locations.find())

    results: list[dict] = []
    for item in data:
        item["id"] = str(item.get("_id"))
        item.pop("_id", None)
        results.append(item)

    return results
