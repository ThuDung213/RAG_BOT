"""Tạo document cho User trước khi lưu vào MongoDB.

Chuẩn hoá `createdAt`/`updatedAt` và giá trị mặc định.
"""

from datetime import datetime, timezone
from typing import Dict, Any


def user_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Tạo document cho User từ payload đầu vào"""
    now = datetime.now(timezone.utc)
    status = payload.get("status") or "active"
    block = payload.get("block")
    if block is None:
        block = {"isBlocked": False}
    doc = {
        **payload,
        "createdAt": payload.get("createdAt", now),
        "updatedAt": payload.get("updatedAt", now),
        "role": payload.get("role", "user"),
        "status": status,
        "block": block,
        # only set when user successfully logs in
        "lastLoginAt": payload.get("lastLoginAt"),
    }
    return doc
