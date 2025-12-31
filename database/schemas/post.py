"""Pydantic schemas cho Post"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Literal
from datetime import datetime


class PostBase(BaseModel):
    """Trường dùng khi tạo/cập nhật bài viết."""
    content: str
    link: Optional[str] = None
    images: Optional[List[str]] = []


class PostCreate(PostBase):
    """Input khi tạo bài; `userId` thường lấy từ auth token."""
    authorId: Optional[str] = None


class PostResponse(PostBase):
    """Response cho post theo sơ đồ lớp."""
    id: str
    authorId: str
    likeCount: int = 0
    commentCount: int = 0
    status: Literal["pending", "approved", "need_edit", "rejected"] = "pending"
    flags: Optional[List[str]] = []
    reportCount: int = 0
    reportReasons: Optional[Dict[str, str]] = {}
    moderation_feedback: Optional[str] = None
    rejected_reason: Optional[str] = None
    moderated_by: Optional[str] = None
    moderated_at: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime
