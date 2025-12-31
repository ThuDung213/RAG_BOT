"""Tạo document cho Gallery trước khi lưu vào MongoDB
Thuộc tính: `year`, `images` (mảng object), `modifiedBy`, `createdAt`, `updatedAt`.
"""
from datetime import datetime
from typing import Dict, Any, List


def gallery_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow()
    images: List[Dict[str, Any]] = payload.get("images") or []

    doc = {
        **payload,
        "year": payload.get("year") if payload.get("year") is not None else None,
        "images": images,
        "modifiedBy": payload.get("modifiedBy"),
        "createdAt": payload.get("createdAt", now),
        "updatedAt": payload.get("updatedAt", now),
    }

    return doc
