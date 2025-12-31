"""Tạo document cho User trước khi lưu vào MongoDB.

Chuẩn hoá `createdAt`/`updatedAt` và giá trị mặc định.
"""

from datetime import datetime
from typing import Dict, Any


def user_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Tạo document cho User từ payload đầu vào"""
    now = datetime.utcnow()
    doc = {
        **payload,
        "createdAt": payload.get("createdAt", now),
        "updatedAt": payload.get("updatedAt", now),
        "role": payload.get("role", "user"),
    }
    return doc
