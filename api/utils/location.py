from fastapi import UploadFile, HTTPException
from typing import List
from api.utils.community import cloudinary_init
import asyncio


async def upload_files_to_cloudinary(files: List[UploadFile], folder: str) -> List[dict]:
    """Upload files to Cloudinary and return list of image metadata dicts.

    This implementation reads file bytes first and then uploads in parallel
    using thread workers (asyncio.to_thread) because cloudinary.uploader.upload
    is a blocking call.
    """
    cloudinary_init()
    try:
        from cloudinary import uploader  # type: ignore
    except Exception:
        raise HTTPException(status_code=500, detail="Missing dependency: cloudinary")

    # Read and validate all files first (preserve the original filenames)
    file_datas = []
    original_filenames: List[str] = []
    for f in files:
        if not (f.content_type or "").startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Invalid content_type: {f.content_type}")
        data = await f.read()
        # Allow up to 10MB per file (frontend shows 10MB)
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 10MB each)")
        file_datas.append(data)
        original_filenames.append(f.filename)

    def _upload(data_bytes):
        return uploader.upload(
            data_bytes,
            folder=folder,
            resource_type="image",
            unique_filename=True,
            overwrite=False,
        )

    upload_tasks = [asyncio.to_thread(_upload, d) for d in file_datas]
    try:
        results = await asyncio.gather(*upload_tasks)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cloudinary upload failed: {e}")

    uploaded = []
    for idx, res in enumerate(results):
        original_filename = original_filenames[idx] if idx < len(original_filenames) else None
        uploaded.append(
            {
                "url": res.get("secure_url") or res.get("url"),
                "publicId": res.get("public_id"),
                # Keep the exact client-uploaded filename for FE caption mapping.
                "originalFilename": original_filename,
                "filename": original_filename,
                "width": res.get("width"),
                "height": res.get("height"),
                "bytes": res.get("bytes"),
                "format": res.get("format"),
            }
        )

    return uploaded


def delete_cloudinary_images(public_ids: List[str]) -> int:
    """Delete images from Cloudinary by public_id. Returns number deleted (best-effort)."""
    if not public_ids:
        return 0

    cloudinary_init()
    try:
        from cloudinary import uploader  # type: ignore
    except Exception:
        raise HTTPException(status_code=500, detail="Missing dependency: cloudinary")

    deleted = 0
    for pid in public_ids:
        if not pid:
            continue
        try:
            # resource_type=image by default
            res = uploader.destroy(pid)
            # cloudinary destroy returns dict with 'result': 'ok' or 'not found'
            if res and res.get("result") in ("ok", "not found"):
                deleted += 1
        except Exception:
            # don't raise; best-effort delete
            continue

    return deleted
