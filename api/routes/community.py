from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from pymongo.errors import DuplicateKeyError

from database.mongo import users, posts, comments, post_likes, post_reports
from api.routes.auth.user_auth import get_current_user  # trả về email từ JWT

from database.schemas.community import (
    CreateCommentPayload,
    CreatePostPayload,
    ReportPostPayload,
    UpdateCommentPayload,
    UpdatePostPayload,
)
from api.utils.community import (
    cloudinary_init,
    cloudinary_is_configured,
    now_utc,
    oid,
    start_of_utc_day,
    to_post_ui,
    to_utc_iso,
    user_by_email,
)

router = APIRouter(prefix="/community", tags=["Community"])


# ----------------------------
# Endpoints
# ----------------------------
@router.post("/uploads", status_code=status.HTTP_201_CREATED)
async def upload_images(
    files: list[UploadFile] = File(...),
    current_email: str = Depends(get_current_user),
):
    """Upload nhiều ảnh lên Cloudinary.

    Flow khuyến nghị:
    1) FE gọi endpoint này để upload ảnh -> nhận images[] (url/publicId)
    2) FE gửi images[] vào POST /community/posts để tạo bài
    """
    u = user_by_email(current_email)
    cloudinary_init()

    if not files:
        raise HTTPException(status_code=400, detail="No files")
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Max 10 files per request")

    try:
        from cloudinary import uploader  # type: ignore
    except Exception:
        raise HTTPException(status_code=500, detail="Missing dependency: cloudinary")

    uploaded: list[dict[str, Any]] = []
    folder = f"rag_bot/posts/{str(u['_id'])}"

    for f in files:
        if not (f.content_type or "").startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Invalid content_type: {f.content_type}")

        data = await f.read()
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 5MB each)")

        try:
            res = uploader.upload(
                data,
                folder=folder,
                resource_type="image",
                unique_filename=True,
                overwrite=False,
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Cloudinary upload failed: {e}")

        uploaded.append(
            {
                "url": res.get("secure_url") or res.get("url"),
                "publicId": res.get("public_id"),
                "width": res.get("width"),
                "height": res.get("height"),
                "bytes": res.get("bytes"),
                "format": res.get("format"),
            }
        )

    return {"images": uploaded}


@router.get("/posts")
def list_posts(
    limit: int = Query(20, ge=1, le=50),
    cursor: Optional[str] = None,
    current_email: str = Depends(get_current_user),
):
    """
    Feed posts mới nhất. Cursor là postId (_id) để phân trang kiểu "infinite scroll".
    Trả về createdAt (FE tự render '2 giờ trước').
    """
    current_user = user_by_email(current_email)

    # Normal users should only see approved posts.
    # Backward-compatible: old documents without `status` are treated as approved.
    # Also exclude soft-deleted posts.
    q: dict[str, Any] = {
        "$and": [
            {"$or": [{"status": "approved"}, {"status": {"$exists": False}}]},
            {"deletedAt": {"$exists": False}},
        ]
    }
    if cursor:
        q["$and"].append({"_id": {"$lt": oid(cursor)}})

    post_list = list(posts.find(q).sort([("_id", -1)]).limit(limit))

    # load authors
    author_ids = list({p.get("authorId") for p in post_list if p.get("authorId")})
    author_map = {u["_id"]: u for u in users.find({"_id": {"$in": author_ids}})}

    # compute isLiked
    post_ids = [p["_id"] for p in post_list]
    liked = set()
    if post_ids:
        for lk in post_likes.find({"userId": current_user["_id"], "postId": {"$in": post_ids}}):
            liked.add(lk["postId"])

    items = []
    for p in post_list:
        a = author_map.get(p.get("authorId"), {})
        items.append(to_post_ui(p, a, p["_id"] in liked))

    next_cursor = str(post_list[-1]["_id"]) if post_list else None
    return {"items": items, "nextCursor": next_cursor}


@router.get("/posts/mine")
def list_my_posts(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    cursor: Optional[str] = None,
    current_email: str = Depends(get_current_user),
):
    """Return current user's posts across all statuses."""
    current_user = user_by_email(current_email)

    q: dict[str, Any] = {"authorId": current_user["_id"]}
    cur = posts.find(q).sort([("_id", -1)])
    if cursor:
        # cursor-based pagination (backward compatible)
        q["_id"] = {"$lt": oid(cursor)}
        cur = posts.find(q).sort([("_id", -1)])
    else:
        # offset-based pagination (required by FE)
        cur = cur.skip(offset)

    post_list = list(cur.limit(limit))
    post_ids = [p["_id"] for p in post_list]

    liked = set()
    if post_ids:
        for lk in post_likes.find({"userId": current_user["_id"], "postId": {"$in": post_ids}}):
            liked.add(lk["postId"])

    items = [to_post_ui(p, current_user, p["_id"] in liked) for p in post_list]
    next_cursor = str(post_list[-1]["_id"]) if post_list else None
    return {"items": items, "nextCursor": next_cursor}


@router.post("/posts", status_code=status.HTTP_201_CREATED)
def create_post(payload: CreatePostPayload, current_email: str = Depends(get_current_user)):
    u = user_by_email(current_email)

    doc = {
        "authorId": u["_id"],
        "content": payload.content.strip(),
        "link": payload.link.model_dump() if payload.link else None,
        "images": [img.model_dump() for img in payload.images] if payload.images else [],
        "likeCount": 0,
        "commentCount": 0,
        "status": "pending",
        "flags": [],
        "reportCount": 0,
        "reportReasons": {},
        "moderation_feedback": None,
        "rejected_reason": None,
        "moderated_by": None,
        "moderated_at": None,
        "approved_at": None,
        "createdAt": now_utc(),
        "updatedAt": now_utc(),
    }
    res = posts.insert_one(doc)
    return {"id": str(res.inserted_id)}


@router.post("/posts/{post_id}/report")
def report_post(
    post_id: str,
    payload: ReportPostPayload,
    current_email: str = Depends(get_current_user),
):
    """Report a community post (requires user login).

    Minimal logic:
    - Validate reason; if reason=other then note is required.
    - Prevent duplicates via unique (postId, reporterId).
    - Persist to post_reports.
    """
    reporter = user_by_email(current_email)
    pid = oid(post_id)

    if not posts.find_one({"_id": pid}):
        raise HTTPException(status_code=404, detail="Post not found")

    # Basic rate limit: reports per user per UTC day.
    # Keep it conservative; can be tuned via env.
    limit_per_day = int(os.getenv("REPORTS_PER_DAY_LIMIT", "10"))
    today = start_of_utc_day(now_utc())
    used_today = post_reports.count_documents({"reporterId": reporter["_id"], "createdAt": {"$gte": today}})
    if used_today >= limit_per_day:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    report_doc = {
        "postId": pid,
        "reporterId": reporter["_id"],
        "reason": payload.reason,
        "note": (payload.note or "").strip() or None,
        "status": "open",
        "resolvedAt": None,
        "resolvedBy": None,
        "resolution": None,
        "createdAt": now_utc(),
    }

    try:
        res = post_reports.insert_one(report_doc)
        # Recommended: "queue" to admin by marking the post as reported + keeping counters.
        posts.update_one(
            {"_id": pid},
            {
                "$addToSet": {"flags": "reported"},
                "$inc": {"reportCount": 1, f"reportReasons.{payload.reason}": 1},
                "$set": {"updatedAt": now_utc()},
            },
        )
        return {
            "id": str(res.inserted_id),
            "created": True,
            "status": "reported",
            "message": "Report created",
        }
    except DuplicateKeyError:
        # Idempotent: already reported by this user.
        existing = post_reports.find_one({"postId": pid, "reporterId": reporter["_id"]})
        return {
            "id": str(existing["_id"]) if existing else None,
            "created": False,
            "status": "already_reported",
            "message": "You already reported this post",
        }


@router.patch("/posts/{post_id}", status_code=status.HTTP_200_OK)
def edit_post(post_id: str, payload: UpdatePostPayload, current_email: str = Depends(get_current_user)):
    """Chỉ tác giả mới được sửa bài viết."""
    u = user_by_email(current_email)
    pid = oid(post_id)

    p = posts.find_one({"_id": pid})
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")
    if p.get("authorId") != u["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    update: dict[str, Any] = {"updatedAt": now_utc()}
    if payload.content is not None:
        update["content"] = payload.content.strip()
    if payload.link is not None:
        update["link"] = payload.link.model_dump()
    if payload.images is not None:
        update["images"] = [img.model_dump() for img in payload.images]

    # UpdatePostPayload already validates at least one field, but keep safe.
    if len(update) == 1:
        raise HTTPException(status_code=400, detail="No fields to update")

    # If post was requested to edit by moderation, treat this edit as a resubmission.
    if (p.get("status") or "approved") == "need_edit":
        update["status"] = "pending"
        # Keep the history in moderation_logs; clear current fields.
        update["moderation_feedback"] = None
        update["rejected_reason"] = None
        update["moderated_by"] = None
        update["moderated_at"] = None
        update["approved_at"] = None

    posts.update_one({"_id": pid}, {"$set": update})
    p2 = posts.find_one({"_id": pid})
    is_liked = bool(post_likes.find_one({"postId": pid, "userId": u["_id"]}))
    return {"item": to_post_ui(p2, u, is_liked)}


@router.delete("/posts/{post_id}", status_code=status.HTTP_200_OK)
def delete_post(post_id: str, current_email: str = Depends(get_current_user)):
    """Chỉ tác giả mới được xoá bài viết. Khi xoá sẽ dọn comments/likes liên quan."""
    u = user_by_email(current_email)
    pid = oid(post_id)

    p = posts.find_one({"_id": pid})
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")
    if p.get("authorId") != u["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    deleted_cloudinary = 0
    if cloudinary_is_configured():
        try:
            cloudinary_init()
            from cloudinary import uploader  # type: ignore

            for img in (p.get("images") or []):
                public_id = (img or {}).get("publicId")
                if public_id:
                    try:
                        uploader.destroy(public_id, resource_type="image")
                        deleted_cloudinary += 1
                    except Exception:
                        pass
        except Exception:
            # không chặn việc xoá post nếu Cloudinary lỗi
            pass

    deleted_post = posts.delete_one({"_id": pid}).deleted_count
    deleted_comments = comments.delete_many({"postId": pid}).deleted_count
    deleted_likes = post_likes.delete_many({"postId": pid}).deleted_count

    return {
        "deleted": bool(deleted_post),
        "deletedComments": int(deleted_comments),
        "deletedLikes": int(deleted_likes),
        "deletedCloudinaryImages": int(deleted_cloudinary),
    }


@router.post("/posts/{post_id}/like", status_code=status.HTTP_200_OK)
def like_post(post_id: str, current_email: str = Depends(get_current_user)):
    u = user_by_email(current_email)
    pid = oid(post_id)

    if not posts.find_one({"_id": pid}):
        raise HTTPException(status_code=404, detail="Post not found")

    # unique index (postId,userId) sẽ chặn like trùng
    try:
        post_likes.insert_one({"postId": pid, "userId": u["_id"], "createdAt": now_utc()})
        posts.update_one({"_id": pid}, {"$inc": {"likeCount": 1}})
    except Exception:
        # nếu trùng like, coi như OK
        pass

    p = posts.find_one({"_id": pid})
    return {"likes": int(p.get("likeCount", 0)), "isLiked": True}


@router.delete("/posts/{post_id}/like", status_code=status.HTTP_200_OK)
def unlike_post(post_id: str, current_email: str = Depends(get_current_user)):
    u = user_by_email(current_email)
    pid = oid(post_id)

    deleted = post_likes.delete_one({"postId": pid, "userId": u["_id"]}).deleted_count
    if deleted:
        posts.update_one({"_id": pid, "likeCount": {"$gt": 0}}, {"$inc": {"likeCount": -1}})

    p = posts.find_one({"_id": pid})
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"likes": int(p.get("likeCount", 0)), "isLiked": False}


@router.get("/posts/{post_id}/comments")
def list_comments(
    post_id: str,
    limit: int = Query(20, ge=1, le=50),
    current_email: str = Depends(get_current_user),
):
    pid = oid(post_id)
    if not posts.find_one({"_id": pid}):
        raise HTTPException(status_code=404, detail="Post not found")

    cmts = list(comments.find({"postId": pid}).sort([("createdAt", -1)]).limit(limit))

    # load authors
    author_ids = list({c.get("authorId") for c in cmts if c.get("authorId")})
    author_map = {u["_id"]: u for u in users.find({"_id": {"$in": author_ids}})}

    items = []
    for c in cmts:
        au = author_map.get(c.get("authorId"), {})
        items.append(
            {
                "id": str(c["_id"]),
                "authorId": str(c.get("authorId")) if c.get("authorId") else None,
                "parentId": str(c.get("parentId")) if c.get("parentId") else None,
                "author": au.get("full_name") or au.get("email"),
                "avatar": au.get("avatarUrl"),
                "text": c.get("content", ""),
                "images": c.get("images") or [],
                "createdAt": to_utc_iso(c.get("createdAt")),
                "updatedAt": to_utc_iso(c.get("updatedAt")),
            }
        )
    return {"items": items}


@router.post("/posts/{post_id}/comments", status_code=status.HTTP_201_CREATED)
def create_comment(post_id: str, payload: CreateCommentPayload, current_email: str = Depends(get_current_user)):
    u = user_by_email(current_email)
    pid = oid(post_id)

    if not posts.find_one({"_id": pid}):
        raise HTTPException(status_code=404, detail="Post not found")

    parent_oid = None
    if payload.parentId:
        parent_oid = oid(payload.parentId)
        parent = comments.find_one({"_id": parent_oid, "postId": pid})
        if not parent:
            raise HTTPException(status_code=404, detail="Parent comment not found")

    doc = {
        "postId": pid,
        "authorId": u["_id"],
        "content": payload.text.strip(),
        "images": [img.model_dump() for img in payload.images] if payload.images else [],
        "createdAt": now_utc(),
    }
    if parent_oid:
        doc["parentId"] = parent_oid
    res = comments.insert_one(doc)
    posts.update_one({"_id": pid}, {"$inc": {"commentCount": 1}})
    return {"id": str(res.inserted_id)}


@router.patch("/posts/{post_id}/comments/{comment_id}", status_code=status.HTTP_200_OK)
def edit_comment(
    post_id: str,
    comment_id: str,
    payload: UpdateCommentPayload,
    current_email: str = Depends(get_current_user),
):
    """Chỉ tác giả mới được sửa comment. Hỗ trợ threaded comments qua parentId."""
    u = user_by_email(current_email)
    pid = oid(post_id)
    cid = oid(comment_id)

    if not posts.find_one({"_id": pid}):
        raise HTTPException(status_code=404, detail="Post not found")

    c = comments.find_one({"_id": cid, "postId": pid})
    if not c:
        raise HTTPException(status_code=404, detail="Comment not found")
    if c.get("authorId") != u["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    update: dict[str, Any] = {"updatedAt": now_utc()}
    if payload.text is not None:
        update["content"] = payload.text.strip()
    if payload.images is not None:
        update["images"] = [img.model_dump() for img in payload.images]

    if len(update) == 1:
        raise HTTPException(status_code=400, detail="No fields to update")

    comments.update_one({"_id": cid}, {"$set": update})

    c2 = comments.find_one({"_id": cid, "postId": pid})
    return {
        "item": {
            "id": str(c2["_id"]),
            "postId": str(pid),
            "parentId": str(c2.get("parentId")) if c2.get("parentId") else None,
            "authorId": str(c2.get("authorId")) if c2.get("authorId") else None,
            "text": c2.get("content", ""),
            "images": c2.get("images") or [],
            "createdAt": to_utc_iso(c2.get("createdAt")),
            "updatedAt": to_utc_iso(c2.get("updatedAt")),
        }
    }


@router.delete("/posts/{post_id}/comments/{comment_id}", status_code=status.HTTP_200_OK)
def delete_comment(
    post_id: str,
    comment_id: str,
    current_email: str = Depends(get_current_user),
):
    """Chỉ tác giả mới được xoá comment.

    Quy tắc thread (2 cấp):
    - Nếu xoá reply (cấp 2): xoá đúng 1 comment.
    - Nếu xoá root (cấp 1): xoá luôn tất cả replies con (để tránh orphan).
    """
    u = user_by_email(current_email)
    pid = oid(post_id)
    cid = oid(comment_id)

    if not posts.find_one({"_id": pid}):
        raise HTTPException(status_code=404, detail="Post not found")

    c = comments.find_one({"_id": cid, "postId": pid})
    if not c:
        raise HTTPException(status_code=404, detail="Comment not found")
    if c.get("authorId") != u["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    deleted_replies = 0
    # root comment if no parentId
    if not c.get("parentId"):
        deleted_replies = comments.delete_many({"postId": pid, "parentId": cid}).deleted_count

    deleted_root = comments.delete_one({"_id": cid, "postId": pid}).deleted_count
    deleted_total = int(deleted_root) + int(deleted_replies)

    if deleted_total:
        # keep commentCount >= 0
        res = posts.update_one(
            {"_id": pid, "commentCount": {"$gte": deleted_total}},
            {"$inc": {"commentCount": -deleted_total}},
        )
        if res.matched_count == 0:
            posts.update_one({"_id": pid}, {"$set": {"commentCount": 0}})

    return {
        "deleted": bool(deleted_root),
        "deletedReplies": int(deleted_replies),
        "deletedTotal": int(deleted_total),
    }