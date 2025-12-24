from typing import List, Optional
from pydantic import BaseModel, Field


class Image(BaseModel):
    url: str
    caption: Optional[str] = ""
    location: Optional[str] = ""
    verified: Optional[bool] = False


class Gallery(BaseModel):
    year: int = Field(..., example=1970)
    images: List[Image]
