from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CommentCreate(BaseModel):
    """Input khi tạo comment."""
    postId: str
    userId: str
    content: str
    images: Optional[List[str]] = []


class CommentResponse(BaseModel):
    """Response cho comment lưu trong DB."""
    id: str
    postId: str
    userId: str
    content: str
    images: Optional[List[str]] = []
    createdAt: datetime
