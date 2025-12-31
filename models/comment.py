"""Tạo document cho Comment trước khi lưu vào MongoDB."""
from datetime import datetime
from typing import Dict, Any, Optional


def comment_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Trả về document comment sẵn sàng lưu
    - Giữ `parentId` nếu là reply.
    """
    now = datetime.utcnow()
    doc: Dict[str, Any] = {
        **payload,
        "createdAt": payload.get("createdAt", now),
    }

    if payload.get("updatedAt"):
        doc["updatedAt"] = payload.get("updatedAt")

    # đảm bảo trường images tồn tại (mảng) và có userId, postId
    doc["images"] = payload.get("images", [])
    doc["userId"] = payload.get("userId")
    doc["postId"] = payload.get("postId")

    return doc
