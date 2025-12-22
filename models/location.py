from datetime import datetime

def location_document(payload: dict):
    return {
        **payload,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
