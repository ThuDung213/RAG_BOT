from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, cast

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from api.routes.auth.admin_auth import get_current_admin
from api.utils.community import now_utc, oid, to_utc_iso
from database.mongo import audit_logs, users
from database.schemas.admin_users import LockUserPayload, UnlockUserPayload

router = APIRouter(prefix="/admin", tags=["Admin Users"])


# ----------------------------
# Helpers
# ----------------------------
ALLOWED_STATUS = {"active", "blocked"}


def _json_safe(v: Any) -> Any:
    """Convert Mongo/Python values to JSON-serializable primitives."""
    if v is None:
        return None
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, datetime):
        return to_utc_iso(v)
    if isinstance(v, dict):
        return {str(k): _json_safe(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    return v


def _parse_until(until: Optional[str]) -> Optional[datetime]:
    if until is None:
        return None
    s = until.strip()
    if not s:
        return None

    # Accept ISO strings with trailing Z
    try:
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(s)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid until")

    # Normalize to UTC (aware)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


def _user_public(u: dict) -> dict:
    block = u.get("block") or {}
    status_val = u.get("status") or ("blocked" if block.get("isBlocked") else "active")
    if status_val not in ALLOWED_STATUS:
        status_val = "active"

    return {
        "id": str(u.get("_id")),
        "email": u.get("email"),
        "full_name": u.get("full_name"),
        "role": u.get("role") or "user",
        "avatarUrl": u.get("avatarUrl"),
        "status": status_val,
        "block": {
            "isBlocked": bool(block.get("isBlocked")) if block else (status_val == "blocked"),
            "reason": block.get("reason"),
            "blockedAt": to_utc_iso(block.get("blockedAt")),
            "blockedUntil": to_utc_iso(block.get("blockedUntil")),
            "blockedBy": str(block.get("blockedBy")) if block.get("blockedBy") else None,
        },
        "createdAt": to_utc_iso(u.get("createdAt")),
        "updatedAt": to_utc_iso(u.get("updatedAt")),
        "lastLoginAt": to_utc_iso(u.get("lastLoginAt")),
    }


def _audit_public(l: dict) -> dict:
    return {
        "id": str(l.get("_id")),
        "actorId": str(l.get("actorId")) if l.get("actorId") else None,
        "action": l.get("action"),
        "targetUserId": str(l.get("targetUserId")) if l.get("targetUserId") else None,
        "reason": l.get("reason"),
        "before": _json_safe(l.get("before") or {}),
        "after": _json_safe(l.get("after") or {}),
        "createdAt": to_utc_iso(l.get("createdAt")),
    }


def _insert_audit(
    *,
    actor_id: ObjectId,
    action: str,
    target_user_id: ObjectId,
    reason: str,
    before: dict,
    after: dict,
) -> None:
    audit_logs.insert_one(
        {
            "actorId": actor_id,
            "action": action,
            "targetUserId": target_user_id,
            "reason": reason,
            "before": _json_safe(before),
            "after": _json_safe(after),
            "createdAt": now_utc(),
        }
    )


# ----------------------------
# Endpoints
# ----------------------------
@router.get("/users")
def admin_list_users(
    search: Optional[str] = None,
    status: Optional[str] = Query(default=None),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _admin: dict = Depends(get_current_admin),
):
    conditions: list[dict[str, Any]] = []

    if status is not None:
        status = status.strip()
        if status and status not in ALLOWED_STATUS:
            raise HTTPException(status_code=400, detail="Invalid status")
        if status == "blocked":
            # Support legacy users where status might be missing but block.isBlocked is true.
            conditions.append({"$or": [{"status": "blocked"}, {"block.isBlocked": True}]})
        elif status == "active":
            conditions.append(
                {
                    "$and": [
                        {"$or": [{"status": "active"}, {"status": {"$exists": False}}, {"status": None}]},
                        {"$or": [{"block.isBlocked": {"$exists": False}}, {"block.isBlocked": False}]},
                    ]
                }
            )

    if search:
        s = search.strip()
        if s:
            conditions.append(
                {
                    "$or": [
                        {"email": {"$regex": s, "$options": "i"}},
                        {"full_name": {"$regex": s, "$options": "i"}},
                    ]
                }
            )

    q: dict[str, Any] = conditions[0] if len(conditions) == 1 else ({"$and": conditions} if conditions else {})

    total = int(users.count_documents(q))

    cur = users.find(q, {"password": 0}).sort([("createdAt", -1), ("_id", -1)]).skip(offset).limit(limit)

    items = [_user_public(u) for u in cur]
    return {"items": items, "total": total}


@router.get("/users/{userId}")
def admin_get_user(
    userId: str,
    _admin: dict = Depends(get_current_admin),
):
    uid = oid(userId)
    u = users.find_one({"_id": uid}, {"password": 0})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_public(u)


@router.patch("/users/{userId}/lock")
def admin_lock_user(
    userId: str,
    payload: LockUserPayload,
    admin: dict = Depends(get_current_admin),
):
    uid = oid(userId)
    u0 = users.find_one({"_id": uid})
    if not u0:
        raise HTTPException(status_code=404, detail="User not found")

    until_dt = _parse_until(payload.until)

    admin_id = cast(ObjectId, admin.get("_id"))

    new_block = {
        "isBlocked": True,
        "reason": payload.reason.strip(),
        "blockedAt": now_utc(),
        "blockedUntil": until_dt,
        "blockedBy": admin_id,
    }

    users.update_one(
        {"_id": uid},
        {
            "$set": {
                "status": "blocked",
                "block": new_block,
                "updatedAt": now_utc(),
            }
        },
    )

    before = {
        "status": u0.get("status") or "active",
        "block": u0.get("block") or {"isBlocked": False},
    }
    after = {
        "status": "blocked",
        "block": {
            "isBlocked": True,
            "reason": new_block.get("reason"),
            "blockedAt": to_utc_iso(new_block.get("blockedAt")),
            "blockedUntil": to_utc_iso(new_block.get("blockedUntil")),
            "blockedBy": str(admin_id),
        },
    }

    _insert_audit(
        actor_id=admin_id,
        action="USER_LOCK",
        target_user_id=uid,
        reason=payload.reason.strip(),
        before=before,
        after=after,
    )

    u1 = users.find_one({"_id": uid}, {"password": 0})
    return _user_public(u1 or {})


@router.patch("/users/{userId}/unlock")
def admin_unlock_user(
    userId: str,
    payload: UnlockUserPayload,
    admin: dict = Depends(get_current_admin),
):
    uid = oid(userId)
    u0 = users.find_one({"_id": uid})
    if not u0:
        raise HTTPException(status_code=404, detail="User not found")

    admin_id = cast(ObjectId, admin.get("_id"))

    users.update_one(
        {"_id": uid},
        {
            "$set": {
                "status": "active",
                "block": {
                    "isBlocked": False,
                    "reason": None,
                    "blockedAt": None,
                    "blockedUntil": None,
                    "blockedBy": None,
                },
                "updatedAt": now_utc(),
            }
        },
    )

    before = {
        "status": u0.get("status") or "active",
        "block": u0.get("block") or {"isBlocked": False},
    }
    after = {
        "status": "active",
        "block": {"isBlocked": False},
    }

    _insert_audit(
        actor_id=admin_id,
        action="USER_UNLOCK",
        target_user_id=uid,
        reason=payload.reason.strip(),
        before=before,
        after=after,
    )

    u1 = users.find_one({"_id": uid}, {"password": 0})
    return _user_public(u1 or {})


@router.get("/users/{userId}/audit-logs")
def admin_user_audit_logs(
    userId: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    withTotal: bool = Query(True),
    _admin: dict = Depends(get_current_admin),
):
    uid = oid(userId)

    q = {"targetUserId": uid}

    cur = (
        audit_logs.find(q)
        .sort([("createdAt", -1), ("_id", -1)])
        .skip(offset)
        .limit(limit)
    )

    items = [_audit_public(l) for l in cur]

    if withTotal:
        total = int(audit_logs.count_documents(q))
        return {"items": items, "total": total}

    return {"items": items}
