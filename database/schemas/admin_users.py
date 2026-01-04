from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LockUserPayload(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    # ISO string, e.g. "2026-01-10T00:00:00Z" (optional)
    until: Optional[str] = None


class UnlockUserPayload(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
