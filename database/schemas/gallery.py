from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Image(BaseModel):
    url: str
    publicId: Optional[str] = None
    year: Optional[int] = None
    caption: Optional[str] = ""
    location: Optional[str] = ""
    verified: Optional[bool] = False
    width: Optional[int] = None
    height: Optional[int] = None
    bytes: Optional[int] = None
    format: Optional[str] = None


class GalleryBase(BaseModel):
    year: int
    images: List[Image]


class GalleryCreate(GalleryBase):
    """Schema khi tạo gallery"""
    year: int = Field(gt=2000, lt=2100)
    modifiedBy: Optional[str] = None


class GalleryResponse(GalleryBase):
    """Schema trả về cho gallery"""
    id: str
    modifiedBy: Optional[str] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
