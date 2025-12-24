from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database.mongo import locations
from core.security.security import decode_admin_token
from database.schemas.locations import LocationCreate, LocationResponse
from models.location import location_document

router = APIRouter(prefix="/admin", tags=["Admin Locations"])
security = HTTPBearer()

def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return decode_admin_token(credentials.credentials)

@router.post("/locations/create", status_code=status.HTTP_201_CREATED)
def create_location(
    payload: LocationCreate,
    admin_email: str = Depends(get_current_admin),
):
    """
    Create new historical location (Admin only)
    """

    data = location_document({
        **payload.dict(),
        "createdBy": admin_email,
    })

    result = locations.insert_one(data)

    if not result.inserted_id:
        raise HTTPException(
            status_code=400,
            detail="Create location failed"
        )

    return {
        "message": "Location created successfully",
        "id": str(result.inserted_id),
    }
    
# Lấy danh sách địa điểm
@router.get("/locations", response_model=list[LocationResponse])
def get_locations():
    data = list(locations.find())

    results = []
    for item in data:
        item["id"] = str(item["_id"])
        del item["_id"]
        results.append(item)

    return results