from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class NeedEditPayload(BaseModel):
    feedback: str = Field(min_length=1, max_length=2000)


class RejectPayload(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


class DeletePostPayload(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)
