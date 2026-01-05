from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from bson.objectid import ObjectId

from database.mongo import locations
from core.security.security import decode_admin_token
from database.schemas.locations import LocationCreate, LocationResponse, LocationUpdate
from datetime import datetime
from models.location import location_document
from fastapi import File, UploadFile, Form, Request
import json
from api.utils.location import upload_files_to_cloudinary, delete_cloudinary_images
from typing import Any

router = APIRouter(prefix="/admin", tags=["Admin Locations"])
security = HTTPBearer()

def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return decode_admin_token(credentials.credentials)

@router.post("/locations/uploads")
async def upload_location_images(
    files: list[UploadFile] = File(...),
    admin_email: str = Depends(get_current_admin),
):
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Max 10 images allowed")

    folder = f"/locations"
    images = await upload_files_to_cloudinary(files, folder)
    return {"images": images}


# Tạo địa điểm mới
@router.post("/locations/create", status_code=201)
async def create_location_json(
    payload: LocationCreate,
    admin_email: str = Depends(get_current_admin),
):
    data = location_document({
        **payload.dict(),
        "createdBy": admin_email,
        "createdAt": datetime.utcnow(),
    })

    try:
        result = locations.insert_one(data)
    except Exception as e:
        # If DB insert failed, try to cleanup any uploaded Cloudinary images referenced
        try:
            imgs = data.get("images") or []
            public_ids = [img.get("publicId") for img in imgs if img and img.get("publicId")]
            if public_ids:
                delete_cloudinary_images(public_ids)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to create location: {e}")

    return {"message": "Location created successfully", "id": str(result.inserted_id)}


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

# Lấy địa điểm theo id
@router.get("/locations/{id}", response_model=LocationResponse)
def get_location_by_id(id: str):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid location id")

    item = locations.find_one({"_id": oid})

    if not item:
        raise HTTPException(status_code=404, detail="Location not found")

    item["id"] = str(item["_id"])
    del item["_id"]

    return item

# Xóa địa điểm
@router.delete("/locations/{id}")
def delete_location(
    id: str,
    admin_email: str = Depends(get_current_admin),
):
    """
    Delete a location by id (Admin only)
    """

    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid location id")

    result = locations.delete_one({"_id": oid})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Location not found")

    return {"message": "Location deleted successfully"}

# Update địa điểm
@router.patch("/locations/{id}")
async def update_location(
    id: str,
    payload: LocationUpdate,
    admin_email: str = Depends(get_current_admin),
):
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid location id")

    update_fields = payload.dict(exclude_unset=True)
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    # fetch original document to determine which images were removed
    orig = locations.find_one({"_id": oid})
    if not orig:
        raise HTTPException(status_code=404, detail="Location not found")

    orig_images = orig.get("images") or []

    update_fields["updatedBy"] = admin_email
    update_fields["updatedAt"] = datetime.utcnow()

    # perform DB update first
    result = locations.update_one({"_id": oid}, {"$set": update_fields})

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Location not found")

    # If caller provided `images`, compute which publicIds were removed and delete them
    try:
        if "images" in update_fields:
            orig_publics = {img.get("publicId") for img in orig_images if img and img.get("publicId")}
            new_images = update_fields.get("images") or []
            new_publics = {img.get("publicId") for img in new_images if img and img.get("publicId")}
            removed = list(orig_publics - new_publics)
            if removed:
                # best-effort delete
                delete_cloudinary_images(removed)
    except Exception:
        # don't fail the whole request for cleanup errors
        pass

    return {"message": "Location updated successfully"}

