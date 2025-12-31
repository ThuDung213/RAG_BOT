from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class LinkPayload(BaseModel):
    title: str
    source: str
    img: Optional[str] = None


class ImagePayload(BaseModel):
    url: str
    publicId: str
    width: Optional[int] = None
    height: Optional[int] = None
    bytes: Optional[int] = None
    format: Optional[str] = None


class CreatePostPayload(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    link: Optional[LinkPayload] = None
    images: list[ImagePayload] = Field(default_factory=list)


class CreateCommentPayload(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    parentId: Optional[str] = None
    images: list[ImagePayload] = Field(default_factory=list)


class UpdateCommentPayload(BaseModel):
    text: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    images: Optional[list[ImagePayload]] = None

    @model_validator(mode="after")
    def validate_has_any_field(self) -> "UpdateCommentPayload":
        if self.text is None and self.images is None:
            raise ValueError("No fields to update")
        return self


class UpdatePostPayload(BaseModel):
    content: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    link: Optional[LinkPayload] = None
    images: Optional[list[ImagePayload]] = None

    @model_validator(mode="after")
    def validate_has_any_field(self) -> "UpdatePostPayload":
        if self.content is None and self.link is None and self.images is None:
            raise ValueError("No fields to update")
        return self


class ReportPostPayload(BaseModel):
    reason: str
    note: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_reason_and_note(self) -> "ReportPostPayload":
        allowed = {"spam", "misinfo", "harassment", "adult", "copyright", "other"}
        if self.reason not in allowed:
            raise ValueError("Invalid reason")
        if self.reason == "other" and not (self.note or "").strip():
            raise ValueError("note is required when reason=other")
        return self
