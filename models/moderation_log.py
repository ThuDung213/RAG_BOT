"""Tạo document cho moderation log trước khi lưu
"""

from datetime import datetime
from typing import Dict, Any


def moderation_log_document(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Trả về document moderation log sẵn sàng lưu
    - Không thay đổi action/ reason.
    """
    now = datetime.utcnow()
    doc = {
        **payload,
        "createdAt": payload.get("createdAt", now),
    }
    return doc
