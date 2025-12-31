"""Tạo document cho Post trước khi lưu vào MongoDB"""
from datetime import datetime
from typing import Dict, Any


def post_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Trả về document sẵn sàng lưu:
    - Nếu `status` là "published" và thiếu `publishedAt`, gán bằng thời điểm hiện tại.
    """
    now = datetime.utcnow()
    doc = {
        **payload,
        "createdAt": payload.get("createdAt", now),
        "updatedAt": payload.get("updatedAt", now),
        "status": payload.get("status", "pending"),
        "likeCount": int(payload.get("likeCount", 0)),
        "commentCount": int(payload.get("commentCount", 0)),
        "reportCount": int(payload.get("reportCount", 0)),
        "images": payload.get("images", []),
        "flags": payload.get("flags", []),
        "reportReasons": payload.get("reportReasons", {}),
        "moderation_feedback": payload.get("moderation_feedback"),
        "rejected_reason": payload.get("rejected_reason"),
        "moderated_by": payload.get("moderated_by"),
        "moderated_at": payload.get("moderated_at"),
    }

    return doc
