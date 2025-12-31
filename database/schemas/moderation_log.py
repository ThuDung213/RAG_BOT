from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class ModerationLogCreate(BaseModel):
    """Input for creating a moderation log entry."""
    postId: str
    adminId: str
    action: Literal["removed", "restored", "flagged", "note"]
    reason: Optional[str] = None


class ModerationLogResponse(ModerationLogCreate):
    """Response schema for a stored moderation log entry."""
    id: str
    createdAt: datetime
