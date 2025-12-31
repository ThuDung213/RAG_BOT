from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class ReportCreate(BaseModel):
    """Input when creating a report."""
    postId: str
    reason: str
    details: Optional[str] = None


class ReportResponse(BaseModel):
    """Response representation for a report."""
    id: str
    postId: str
    reporterId: str
    reason: str
    details: Optional[str] = None
    status: Literal["open", "resolved", "dismissed"] = "open"
    createdAt: datetime
    updatedAt: Optional[datetime] = None
