from pydantic import BaseModel
from typing import Optional

class LocationBase(BaseModel):
    siteName: str
    locationType: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    shortDescription: Optional[str] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    history: Optional[str] = None
    keyEvents: Optional[str] = None
    architecture: Optional[str] = None
    significance: Optional[str] = None
    additionalContent: Optional[str] = None


class LocationCreate(LocationBase):
    """Dùng cho POST /admin/locations/create"""
    pass

class LocationResponse(LocationBase):
    """Dùng cho GET"""
    id: str