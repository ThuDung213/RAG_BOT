from pydantic import BaseModel
from typing import Optional, List


class Image(BaseModel):
    url: str
    publicId: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    bytes: Optional[int] = None
    format: Optional[str] = None

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

    # images uploaded via Cloudinary (FE uploads first, then passes images[] here)
    images: Optional[List[Image]] = None


class LocationCreate(LocationBase):
    """Dùng cho POST /admin/locations/create"""
    pass

class LocationResponse(LocationBase):
    """Dùng cho GET"""
    id: str


class LocationUpdate(BaseModel):
    """Dùng cho PATCH/PUT - tất cả trường đều optional cho partial update"""
    siteName: Optional[str] = None
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
    images: Optional[List[Image]] = None