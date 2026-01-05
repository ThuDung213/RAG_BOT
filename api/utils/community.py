from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from fastapi import HTTPException, status

from database.mongo import users


def oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def start_of_utc_day(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def to_utc_iso(dt: Any) -> Optional[str]:
    """Serialize datetime with explicit UTC offset.

    PyMongo commonly returns naive datetimes (tzinfo=None) that represent UTC.
    If FE parses a naive ISO string, it will assume local time (e.g., UTC+7),
    making timestamps appear ~7 hours old. We normalize to UTC and include TZ.
    """
    if dt is None:
        return None
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def user_by_email(email: str) -> dict:
    u = users.find_one({"email": email})
    if not u:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return u


def to_post_ui(post: dict, author: dict, is_liked: bool) -> dict:
    link = post.get("link") or None
    author_id = post.get("authorId")
    status_val = post.get("status") or "approved"
    flags = post.get("flags") or []
    # For user-facing timestamps, prefer the original publish time if present.
    # `published_at` is intended to be the first time the post became public.
    # `approved_at` may change on re-approvals after edits.
    approved_dt = post.get("published_at") or post.get("approved_at")
    # Backward-compatible: old approved posts (no status) won't have approved_at.
    if approved_dt is None and post.get("status") is None:
        approved_dt = post.get("createdAt")
    return {
        "id": str(post["_id"]),
        "authorId": str(author_id) if author_id else None,
        "author": author.get("full_name") or author.get("email"),
        "avatar": author.get("avatarUrl"),
        "createdAt": to_utc_iso(post.get("createdAt")),
        "approvedAt": to_utc_iso(approved_dt),
        "content": post.get("content", ""),
        "link": link,
        "images": post.get("images") or [],
        "likes": int(post.get("likeCount", 0)),
        "commentCount": int(post.get("commentCount", 0)),
        "isLiked": bool(is_liked),
        "status": status_val,
        "flags": flags,
        "moderation_feedback": post.get("moderation_feedback") if status_val == "need_edit" else None,
        "rejected_reason": post.get("rejected_reason") if status_val == "rejected" else None,
    }


def cloudinary_is_configured() -> bool:
    if os.getenv("CLOUDINARY_URL"):
        return True
    return bool(
        os.getenv("CLOUDINARY_CLOUD_NAME")
        and os.getenv("CLOUDINARY_API_KEY")
        and os.getenv("CLOUDINARY_API_SECRET")
    )


def cloudinary_init() -> None:
    # If env vars are not set, try loading a .env file (optional dependency)
    if not cloudinary_is_configured():
        try:
            from dotenv import load_dotenv  # type: ignore
        except Exception:
            load_dotenv = None

        if load_dotenv:
            # attempt to load .env from repo root
            load_dotenv()

    if not cloudinary_is_configured():
        raise HTTPException(
            status_code=500,
            detail=(
                "Cloudinary is not configured. Set CLOUDINARY_URL or "
                "CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET. "
                "You can place these in a .env file at the project root and install python-dotenv."
            ),
        )
    try:
        import cloudinary  # type: ignore
    except Exception:
        raise HTTPException(status_code=500, detail="Missing dependency: cloudinary")

    if os.getenv("CLOUDINARY_URL"):
        cloudinary.config(secure=True)
        return

    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True,
    )
