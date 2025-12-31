"""Tạo document cho Like trước khi lưu vào MongoDB
Thuộc tính: `postId`, `userId`, `createdAt`.
"""

from datetime import datetime
from typing import Dict, Any


def like_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow()
    doc = {
        **payload,
        "createdAt": payload.get("createdAt", now),
    }
    return doc
