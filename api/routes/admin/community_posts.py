from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, cast

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.routes.auth.admin_auth import get_current_admin
from database.mongo import moderation_logs, posts, users

router = APIRouter(prefix="/admin/community", tags=["Admin Community"])


# ----------------------------
# Helpers
# ----------------------------

def oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_utc_iso(dt: Any) -> Optional[str]:
    if dt is None or not isinstance(dt, datetime):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def to_post_admin_ui(post: dict, author: dict) -> dict:
    status_val = post.get("status") or "approved"
    flags = post.get("flags") or []
    item = {
        "id": str(post["_id"]),
        "author": author.get("full_name") or author.get("email"),
        "createdAt": to_utc_iso(post.get("createdAt")),
        "content": post.get("content", ""),
        "images": post.get("images") or [],
        "link": post.get("link") or None,
        "status": status_val,
        "flags": flags,
    }
    if status_val == "need_edit":
        item["moderation_feedback"] = post.get("moderation_feedback") or ""
    return item


# ----------------------------
# Schemas
# ----------------------------


class NeedEditBody(BaseModel):
    feedback: str = Field(min_length=1, max_length=5000)


class RejectBody(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=5000)


# ----------------------------
# Endpoints
# ----------------------------


@router.get("/posts")
def admin_list_posts(
    status: Optional[str] = Query(default=None, pattern="^(pending|approved|need_edit|rejected)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_admin: dict = Depends(get_current_admin),
):
    q: dict[str, Any] = {}
    if status:
        q["status"] = status

    post_list = list(posts.find(q).sort([("_id", -1)]).skip(offset).limit(limit))

    author_ids = list({p.get("authorId") for p in post_list if p.get("authorId")})
    author_map = {u["_id"]: u for u in users.find({"_id": {"$in": author_ids}})}

    items = []
    for p in post_list:
        author = author_map.get(p.get("authorId"), {})
        items.append(to_post_admin_ui(p, author))

    return {"items": items}


def _write_moderation_log(*, post_id: ObjectId, action: str, note: str, flags_snapshot: list[str], admin_id: ObjectId):
    moderation_logs.insert_one(
        {
            "postId": post_id,
            "action": action,
            "note": note,
            "flags_snapshot": flags_snapshot,
            "adminId": admin_id,
            "createdAt": now_utc(),
        }
    )


@router.post("/posts/{post_id}/approve", status_code=status.HTTP_200_OK)
def admin_approve_post(post_id: str, current_admin: dict = Depends(get_current_admin)):
    pid = oid(post_id)
    p = posts.find_one({"_id": pid})
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")

    admin_id = cast(ObjectId, current_admin.get("_id"))
    flags_snapshot = list(p.get("flags") or [])

    posts.update_one(
        {"_id": pid},
        {
            "$set": {
                "status": "approved",
                "moderated_by": admin_id,
                "moderated_at": now_utc(),
            },
            "$unset": {"moderation_feedback": "", "rejected_reason": ""},
        },
    )

    _write_moderation_log(
        post_id=pid,
        action="approved",
        note="",
        flags_snapshot=flags_snapshot,
        admin_id=admin_id,
    )

    return {"updated": True}


@router.post("/posts/{post_id}/need-edit", status_code=status.HTTP_200_OK)
def admin_need_edit_post(post_id: str, body: NeedEditBody, current_admin: dict = Depends(get_current_admin)):
    pid = oid(post_id)
    p = posts.find_one({"_id": pid})
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")

    admin_id = cast(ObjectId, current_admin.get("_id"))
    flags_snapshot = list(p.get("flags") or [])

    posts.update_one(
        {"_id": pid},
        {
            "$set": {
                "status": "need_edit",
                "moderation_feedback": body.feedback.strip(),
                "moderated_by": admin_id,
                "moderated_at": now_utc(),
            },
            "$unset": {"rejected_reason": ""},
        },
    )

    _write_moderation_log(
        post_id=pid,
        action="need_edit",
        note=body.feedback.strip(),
        flags_snapshot=flags_snapshot,
        admin_id=admin_id,
    )

    return {"updated": True}


@router.post("/posts/{post_id}/reject", status_code=status.HTTP_200_OK)
def admin_reject_post(post_id: str, body: RejectBody, current_admin: dict = Depends(get_current_admin)):
    pid = oid(post_id)
    p = posts.find_one({"_id": pid})
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")

    admin_id = cast(ObjectId, current_admin.get("_id"))
    flags_snapshot = list(p.get("flags") or [])

    reason = (body.reason or "").strip()

    posts.update_one(
        {"_id": pid},
        {
            "$set": {
                "status": "rejected",
                "rejected_reason": reason,
                "moderated_by": admin_id,
                "moderated_at": now_utc(),
            },
            "$unset": {"moderation_feedback": ""},
        },
    )

    _write_moderation_log(
        post_id=pid,
        action="rejected",
        note=reason,
        flags_snapshot=flags_snapshot,
        admin_id=admin_id,
    )

    return {"updated": True}
