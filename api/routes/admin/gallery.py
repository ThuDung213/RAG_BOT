from __future__ import annotations

from typing import List, Optional, Any

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from datetime import datetime
import time
import os
import json

from database.mongo import gallery
from database.schemas.gallery import GalleryCreate, GalleryResponse
from api.utils.location import upload_files_to_cloudinary, delete_cloudinary_images
from core.security.security import decode_admin_token

router = APIRouter(prefix="/admin", tags=["Admin Gallery"])
security = HTTPBearer()


def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return decode_admin_token(credentials.credentials)


@router.get("/gallery", response_model=List[GalleryResponse])
def admin_get_all_galleries(limit: int = 100, admin_email: str = Depends(get_current_admin)):
    docs = list(gallery.find({}).sort("year", -1).limit(limit))
    items = []
    for d in docs:
        items.append(
            {
                "id": str(d.get("_id")),
                "year": d.get("year"),
                "images": d.get("images") or [],
                "modifiedBy": d.get("modifiedBy"),
                "createdAt": d.get("createdAt"),
                "updatedAt": d.get("updatedAt"),
            }
        )
    return items


@router.post("/gallery/uploads")
async def admin_upload_gallery_images(
    files: List[UploadFile] = File(...),
    year: Optional[int] = Form(None),
    meta: Optional[str] = Form(None),
    admin_email: str = Depends(get_current_admin),
):
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Max 50 images allowed")

    folder = f"gallery/{year or 'unknown'}"
    start = time.time()
    uploaded = await upload_files_to_cloudinary(files, folder)
    upload_time = time.time() - start
    print(f"[admin_upload_gallery_images] uploaded {len(uploaded)} files in {upload_time:.2f}s to folder={folder}")

    meta_map: dict = {}
    if meta:
        try:
            parsed = json.loads(meta)
            if isinstance(parsed, dict):
                meta_map = parsed
            else:
                raise ValueError("meta must be a JSON object")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid meta JSON: {e}")

    # Normalize items to store in DB (include metadata + publicId)
    images_to_store = []
    now = datetime.utcnow()
    for u in uploaded:
        original_filename = u.get("originalFilename") or u.get("filename")
        caption = ""
        if isinstance(original_filename, str) and original_filename and original_filename in meta_map:
            meta_item = meta_map.get(original_filename)
            if isinstance(meta_item, dict) and isinstance(meta_item.get("caption"), str):
                caption = meta_item.get("caption")
        images_to_store.append(
            {
                "url": u.get("url"),
                "publicId": u.get("publicId"),
                "originalFilename": original_filename,
                "caption": caption,
                "location": "",
                "verified": False,
                "width": u.get("width"),
                "height": u.get("height"),
                "bytes": u.get("bytes"),
                "format": u.get("format"),
            }
        )

    # Upsert gallery document for the year (append images)
    if year:
        db_start = time.time()
        res = gallery.update_one(
            {"year": year},
            {
                "$set": {"modifiedBy": admin_email, "updatedAt": now, "year": year},
                "$push": {"images": {"$each": images_to_store}},
                "$setOnInsert": {"createdAt": now},
            },
            upsert=True,
        )
        db_time = time.time() - db_start
        print(f"[admin_upload_gallery_images] DB upsert time: {db_time:.2f}s (year={year})")

    return {"images": uploaded}


@router.patch("/gallery/images")
def admin_batch_update_gallery_images(
    payload: list[dict],
    admin_email: str = Depends(get_current_admin),
):
    """Batch update image captions.

    Payload example:
    [{"publicId": "...", "caption": "..."}, ...]
    """
    if not isinstance(payload, list) or not payload:
        raise HTTPException(status_code=400, detail="Payload must be a non-empty list")

    now = datetime.utcnow()
    total_matched = 0
    total_modified = 0
    for item in payload:
        if not isinstance(item, dict):
            continue
        public_id = item.get("publicId")
        caption = item.get("caption")
        if not isinstance(public_id, str) or not public_id:
            continue
        if not isinstance(caption, str):
            continue
        res = gallery.update_one(
            {"images.publicId": public_id},
            {"$set": {"images.$.caption": caption, "modifiedBy": admin_email, "updatedAt": now}},
        )
        total_matched += int(getattr(res, "matched_count", 0) or 0)
        total_modified += int(getattr(res, "modified_count", 0) or 0)

    return {"matchedCount": total_matched, "modifiedCount": total_modified}


@router.delete("/gallery/{public_id:path}")
def admin_delete_gallery_image(public_id: str, admin_email: str = Depends(get_current_admin)):
    # Support deletion by Cloudinary publicId OR by image URL.
    if not public_id:
        raise HTTPException(status_code=400, detail="Missing identifier")

    is_url = public_id.startswith("http://") or public_id.startswith("https://")

    if is_url:
        # treat the param as a URL, pull by images.url
        res = gallery.update_many({"images.url": public_id}, {"$pull": {"images": {"url": public_id}}})
        return {"message": "Deleted by URL from gallery records", "modifiedCount": res.modified_count}
    else:
        # Pull image from all gallery docs that contain the publicId
        res = gallery.update_many({"images.publicId": public_id}, {"$pull": {"images": {"publicId": public_id}}})

        # Best-effort delete from Cloudinary
        try:
            delete_cloudinary_images([public_id])
        except Exception:
            pass

        return {"message": "Deleted from gallery records", "modifiedCount": res.modified_count}


@router.patch("/gallery/image")
def admin_update_gallery_image(
    payload: dict,
    admin_email: str = Depends(get_current_admin),
):
    """
    Update image metadata. Provide either `publicId` or `url` in payload, plus any of: `caption`, `location`, `verified`.
    """
    public_id = payload.get("publicId")
    url = payload.get("url")
    if not public_id and not url:
        raise HTTPException(status_code=400, detail="Provide publicId or url to identify image")

    allowed = {"caption", "location", "verified"}
    set_fields = {}
    for k in allowed:
        if k in payload:
            set_fields[f"images.$.{k}"] = payload[k]

    if not set_fields:
        raise HTTPException(status_code=400, detail="No updatable fields provided")

    # Build filter to match images
    if public_id:
        filter_q = {"images.publicId": public_id}
    else:
        filter_q = {"images.url": url}

    now = datetime.utcnow()
    set_fields["modifiedBy"] = admin_email
    set_fields["updatedAt"] = now

    # Use update_one so we update a single gallery document and the matched array element
    res = gallery.update_one(filter_q, {"$set": set_fields})

    return {"matchedCount": res.matched_count, "modifiedCount": res.modified_count}


@router.post("/cloudinary/sign")
def admin_cloudinary_sign(
    folder: Optional[str] = Form(None),
    admin_email: str = Depends(get_current_admin),
):
    """
    Return a short-lived Cloudinary signature for direct client uploads.
    Client should POST files directly to Cloudinary with the returned `api_key`, `timestamp`, and `signature`.
    """
    # Ensure cloudinary is configured
    from api.utils.community import cloudinary_init

    cloudinary_init()

    try:
        from cloudinary.utils import api_sign_request  # type: ignore
    except Exception:
        raise HTTPException(status_code=500, detail="Missing dependency: cloudinary")

    ts = int(time.time())
    params_to_sign: dict[str, Any] = {"timestamp": ts}
    if folder:
        # Cloudinary expects folder without leading slash
        params_to_sign["folder"] = folder.lstrip("/")

    # Use env var directly for api_secret
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    if not api_secret:
        raise HTTPException(status_code=500, detail="Cloudinary API secret missing")

    signature = api_sign_request(params_to_sign, api_secret)

    return {
        "api_key": os.getenv("CLOUDINARY_API_KEY"),
        "timestamp": ts,
        "signature": signature,
        "cloud_name": os.getenv("CLOUDINARY_CLOUD_NAME"),
    }
