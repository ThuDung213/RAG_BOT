from pydantic import BaseModel
from datetime import datetime


class LikeCreate(BaseModel):
    """Input when a user likes a post."""
    postId: str


class LikeResponse(BaseModel):
    """Returned representation of a like record."""
    id: str
    postId: str
    userId: str
    createdAt: datetime
