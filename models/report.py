"""Tạo document cho Report trước khi lưu vào MongoDB.

Thuộc tính theo sơ đồ: `postId`, `userId`, `reason`, `note`, `status`,
`resolvedAt`, `resolvedBy`, `resolution`, `createdAt`.
"""

from datetime import datetime
from typing import Dict, Any, Optional


def report_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow()
    user_id = payload.get("userId") or payload.get("reporterId")

    doc: Dict[str, Any] = {
        **payload,
        "createdAt": payload.get("createdAt", now),
        "status": payload.get("status", "open"),
        "resolvedAt": payload.get("resolvedAt"),
        "resolvedBy": payload.get("resolvedBy"),
        "resolution": payload.get("resolution"),
        "userId": user_id,
        "reporterId": user_id,
    }

    return doc
