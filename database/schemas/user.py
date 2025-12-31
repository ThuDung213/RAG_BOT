from pydantic import BaseModel, EmailStr
from typing import Optional, Literal
from datetime import datetime


class UserBase(BaseModel):
    """Base fields shared between create and response schemas."""
    full_name: str
    email: EmailStr
    avatarUrl: Optional[str] = None
    bio: Optional[str] = None


class UserCreate(UserBase):
    """Schema used when creating/registering a new user"""
    password: str


class UserResponse(UserBase):
    """Schema returned by GET endpoints representing a stored user."""
    id: str
    role: Literal["user", "admin"] = "user"
    createdAt: datetime
