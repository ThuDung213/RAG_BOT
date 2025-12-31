from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Image(BaseModel):
    url: str
    caption: Optional[str] = ""
    location: Optional[str] = ""
    verified: Optional[bool] = False


class GalleryBase(BaseModel):
    year: int = Field(gt=2000, lt=2100)
    images: List[Image]


class GalleryCreate(GalleryBase):
    """Schema khi tạo gallery"""
    modifiedBy: Optional[str] = None


class GalleryResponse(GalleryBase):
    """Schema trả về cho gallery"""
    id: str
    modifiedBy: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
