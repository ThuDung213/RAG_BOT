from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, cast

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.routes.auth.admin_auth import get_current_admin
from database.mongo import moderation_logs, posts, users, post_reports

router = APIRouter(prefix="/admin/community", tags=["Admin Community"])


# ----------------------------
# Helpers
# ----------------------------
ALLOWED_STATUSES = {"pending", "approved", "need_edit", "rejected"}
ALLOWED_ACTIONS = {"approved", "need_edit", "rejected"}
ALLOWED_REPORT_STATUSES = {"open", "resolved"}


def oid(s: str) -> ObjectId:
    try:
        return ObjectId(s)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_utc_iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _post_to_admin_ui(post: dict, author: dict) -> dict:
    author_id = post.get("authorId")
    status_val = post.get("status") or "pending"
    data = {
        "id": str(post["_id"]),
        "authorId": str(author_id) if author_id else None,
        "author": author.get("full_name") or author.get("email"),
        "avatar": author.get("avatarUrl"),
        "createdAt": to_utc_iso(post.get("createdAt")),
        "approvedAt": to_utc_iso(post.get("approved_at") or post.get("published_at")),
        "content": post.get("content", ""),
        "images": post.get("images") or [],
        "link": post.get("link") or None,
        "status": status_val,
        "flags": post.get("flags") or [],
        # Optional but recommended for admin triage
        "reportCount": int(post.get("reportCount", 0) or 0),
        "flagsSummary": post.get("reportReasons") or {},
    }

    if status_val == "need_edit":
        data["moderation_feedback"] = post.get("moderation_feedback") or ""
    if status_val == "rejected":
        reason = post.get("rejected_reason")
        if reason is not None:
            data["rejected_reason"] = reason

    return data


@router.get("/reports")
def admin_list_reports(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: str = Query("open", alias="status"),
    _admin: dict = Depends(get_current_admin),
):
    """Aggregate reports by post for admin moderation.

    Response shape is designed for FE admin UI:
    - each item = 1 reported post
    - includes post snapshot (author, createdAt, content)
    - timestamps are ISO UTC strings (e.g. 2025-12-21T05:48:29.000Z)
    """
    if status_filter not in ALLOWED_REPORT_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    match_stage = {"$match": {"status": status_filter}}

    # total = number of distinct posts for this status
    total_pipeline = [
        match_stage,
        {"$group": {"_id": "$postId"}},
        {"$count": "total"},
    ]
    total_res = list(post_reports.aggregate(total_pipeline))
    total = int((total_res[0] or {}).get("total", 0)) if total_res else 0

    pipeline = [
        match_stage,
        {
            "$group": {
                "_id": "$postId",
                "reportCount": {"$sum": 1},
                "lastReportedAt": {"$max": "$createdAt"},
                "reasons": {"$push": "$reason"},
            }
        },
        {"$sort": {"lastReportedAt": -1}},
        {"$skip": offset},
        {"$limit": limit},
    ]

    grouped = list(post_reports.aggregate(pipeline))

    # Build reason counts + top reporters in Python to keep pipeline simple.
    items = []
    for g in grouped:
        post_id = g.get("_id")
        reasons = g.get("reasons") or []
        reason_counts: dict[str, int] = {}
        for r in reasons:
            if not r:
                continue
            reason_counts[r] = int(reason_counts.get(r, 0)) + 1

        top_reasons = [
            k
            for k, _v in sorted(reason_counts.items(), key=lambda kv: kv[1], reverse=True)
        ][:3]

        # Enrich with post + author snapshot
        post_doc = posts.find_one({"_id": post_id}) if post_id else None
        author_name = "Unknown"
        author_id_str: Optional[str] = None
        post_created_at = None
        post_content = ""
        post_link = None
        post_images = []
        post_status = None

        if post_doc:
            post_created_at = post_doc.get("createdAt")
            post_content = (post_doc.get("content") or "")
            post_link = post_doc.get("link") or None
            post_images = post_doc.get("images") or []
            post_status = post_doc.get("status") or ("approved" if post_doc.get("status") is None else None)
            author_id = post_doc.get("authorId")
            if author_id:
                author_id_str = str(author_id)
                au = users.find_one({"_id": author_id})
                if au:
                    author_name = au.get("full_name") or au.get("email") or "Unknown"

        # Include recent reports for modal details (bounded to last 50)
        reports_cur = (
            post_reports.find({"postId": post_id, "status": status_filter})
            .sort([("createdAt", -1)])
            .limit(50)
        )
        report_rows = []
        resolved_action: Optional[str] = None
        for r in reports_cur:
            if status_filter == "resolved" and resolved_action is None:
                resolved_action = r.get("resolution")
            report_rows.append(
                {
                    "reporterId": str(r.get("reporterId")) if r.get("reporterId") else None,
                    "reason": r.get("reason"),
                    "note": r.get("note"),
                    "createdAt": to_utc_iso(r.get("createdAt")),
                    # Optional for resolved tab / modal
                    "resolvedAction": r.get("resolution"),
                    "resolvedAt": to_utc_iso(r.get("resolvedAt")),
                }
            )

        items.append(
            {
                "postId": str(post_id) if post_id else None,
                "reportCount": int(g.get("reportCount", 0) or 0),
                "lastReportedAt": to_utc_iso(g.get("lastReportedAt")),
                # for FE: quick chips/badges
                "topReasons": top_reasons,
                # for resolved tab
                "resolvedAction": resolved_action,
                "post": {
                    "id": str(post_doc.get("_id")) if post_doc else None,
                    "authorId": author_id_str,
                    "author": author_name,
                    "createdAt": to_utc_iso(post_created_at),
                    "content": post_content,
                    "link": post_link,
                    "images": post_images,
                    "status": post_status,
                },
                "reports": report_rows,
            }
        )

    return {"items": items, "total": total}


def _insert_moderation_log(
    *,
    post_id: ObjectId,
    action: str,
    note: str,
    flags_snapshot: list[str],
    admin_id: ObjectId,
) -> None:
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


# ----------------------------
# Schemas
# ----------------------------
class NeedEditPayload(BaseModel):
    feedback: str = Field(min_length=1, max_length=2000)


class RejectPayload(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


class DeletePostPayload(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


# ----------------------------
# Endpoints
# ----------------------------
@router.get("/posts")
def admin_list_posts(
    status_filter: str = Query("pending", alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _admin: dict = Depends(get_current_admin),
):
    if status_filter not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    q: dict[str, Any] = {"status": status_filter}

    post_list = list(posts.find(q).sort([("_id", -1)]).skip(offset).limit(limit))

    author_ids = list({p.get("authorId") for p in post_list if p.get("authorId")})
    author_map = {u["_id"]: u for u in users.find({"_id": {"$in": author_ids}})}

    items = []
    for p in post_list:
        a = author_map.get(p.get("authorId"), {})
        items.append(_post_to_admin_ui(p, a))

    return {"items": items}


@router.post("/posts/{post_id}/approve", status_code=status.HTTP_200_OK)
def admin_approve_post(post_id: str, admin: dict = Depends(get_current_admin)):
    pid = oid(post_id)
    p = posts.find_one({"_id": pid})
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")

    flags_snapshot = p.get("flags") or []

    admin_id = cast(ObjectId, admin.get("_id"))

    posts.update_one(
        {"_id": pid},
        {
            "$set": {
                "status": "approved",
                "approved_at": now_utc(),
                "moderation_feedback": None,
                "rejected_reason": None,
                "moderated_by": admin_id,
                "moderated_at": now_utc(),
                "updatedAt": now_utc(),
            }
        },
    )

    _insert_moderation_log(
        post_id=pid,
        action="approved",
        note="",
        flags_snapshot=list(flags_snapshot),
        admin_id=admin_id,
    )

    return {"ok": True}


@router.post("/posts/{post_id}/need-edit", status_code=status.HTTP_200_OK)
def admin_need_edit_post(
    post_id: str,
    payload: NeedEditPayload,
    admin: dict = Depends(get_current_admin),
):
    pid = oid(post_id)
    p = posts.find_one({"_id": pid})
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")

    flags_snapshot = p.get("flags") or []

    feedback = payload.feedback.strip()

    admin_id = cast(ObjectId, admin.get("_id"))

    posts.update_one(
        {"_id": pid},
        {
            "$set": {
                "status": "need_edit",
                "approved_at": None,
                "moderation_feedback": feedback,
                "rejected_reason": None,
                "moderated_by": admin_id,
                "moderated_at": now_utc(),
                "updatedAt": now_utc(),
            }
        },
    )

    _insert_moderation_log(
        post_id=pid,
        action="need_edit",
        note=feedback,
        flags_snapshot=list(flags_snapshot),
        admin_id=admin_id,
    )

    return {"ok": True}


@router.post("/posts/{post_id}/reject", status_code=status.HTTP_200_OK)
def admin_reject_post(
    post_id: str,
    payload: RejectPayload,
    admin: dict = Depends(get_current_admin),
):
    pid = oid(post_id)
    p = posts.find_one({"_id": pid})
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")

    flags_snapshot = p.get("flags") or []

    reason = (payload.reason or "").strip()

    admin_id = cast(ObjectId, admin.get("_id"))

    posts.update_one(
        {"_id": pid},
        {
            "$set": {
                "status": "rejected",
                "approved_at": None,
                "rejected_reason": reason or None,
                "moderation_feedback": None,
                "moderated_by": admin_id,
                "moderated_at": now_utc(),
                "updatedAt": now_utc(),
            }
        },
    )

    _insert_moderation_log(
        post_id=pid,
        action="rejected",
        note=reason,
        flags_snapshot=list(flags_snapshot),
        admin_id=admin_id,
    )

    return {"ok": True}


@router.post("/reports/posts/{post_id}/dismiss", status_code=status.HTTP_200_OK)
def admin_dismiss_reports_for_post(post_id: str, admin: dict = Depends(get_current_admin)):
    """Dismiss (resolve) all OPEN reports for a post.

    - Marks all open reports as resolved with resolution=dismissed
    - Does NOT change post visibility/status
    - Clears the post's reported triage fields (flags/reportCount/reportReasons)
    """
    pid = oid(post_id)
    if not posts.find_one({"_id": pid}):
        raise HTTPException(status_code=404, detail="Post not found")

    admin_id = cast(ObjectId, admin.get("_id"))

    res = post_reports.update_many(
        {"postId": pid, "status": "open"},
        {
            "$set": {
                "status": "resolved",
                "resolvedAt": now_utc(),
                "resolvedBy": admin_id,
                "resolution": "dismissed",
            }
        },
    )

    posts.update_one(
        {"_id": pid},
        {
            "$pull": {"flags": "reported"},
            "$set": {"reportCount": 0, "reportReasons": {}, "updatedAt": now_utc()},
        },
    )

    return {"ok": True, "dismissed": int(res.modified_count)}


@router.delete("/posts/{post_id}", status_code=status.HTTP_200_OK)
def admin_soft_delete_post(
    post_id: str,
    payload: Optional[DeletePostPayload] = None,
    admin: dict = Depends(get_current_admin),
):
    """Soft delete a post (approve report => remove post from user feed).

    Sets: deletedAt, deletedBy, deleteReason.
    Also resolves any open reports for the post as resolution=deleted.
    """
    pid = oid(post_id)
    if not posts.find_one({"_id": pid}):
        raise HTTPException(status_code=404, detail="Post not found")

    reason = ((payload.reason if payload else None) or "").strip() or None

    admin_id = cast(ObjectId, admin.get("_id"))

    posts.update_one(
        {"_id": pid},
        {
            "$set": {
                "deletedAt": now_utc(),
                "deletedBy": admin_id,
                "deletedReason": reason,
                # backward-compatible
                "deleteReason": reason,
                "updatedAt": now_utc(),
            },
            "$pull": {"flags": "reported"},
        },
    )

    post_reports.update_many(
        {"postId": pid, "status": "open"},
        {
            "$set": {
                "status": "resolved",
                "resolvedAt": now_utc(),
                "resolvedBy": admin_id,
                "resolution": "deleted",
            }
        },
    )

    return {"ok": True}
