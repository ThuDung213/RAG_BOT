from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status, Depends, File, UploadFile, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from database.mongo import users
from api.utils.community import now_utc
from models.user import user_document
from core.security.security import (
    create_access_token,
    verify_password,
    get_password_hash,
    decode_admin_token,
)

router = APIRouter(prefix="/users", tags=["Users"])
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Token payload uses the same `sub` field for both admin and user.
    return decode_admin_token(credentials.credentials)


def _user_to_me_response(u: dict) -> dict:
    avatar_url = u.get("avatarUrl") or u.get("avatar_url") or u.get("avatar")
    return {
        "id": str(u.get("_id")),
        "email": u.get("email"),
        "full_name": u.get("full_name"),
        "avatar_url": avatar_url,
    }


def _enforce_password_policy(new_password: str) -> None:
    if not isinstance(new_password, str):
        raise HTTPException(status_code=400, detail="Mật khẩu mới không hợp lệ")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải có ít nhất 8 ký tự")
    has_letter = any(ch.isalpha() for ch in new_password)
    has_digit = any(ch.isdigit() for ch in new_password)
    if not (has_letter and has_digit):
        raise HTTPException(
            status_code=400,
            detail="Mật khẩu mới phải chứa ít nhất 1 chữ và 1 số",
        )


def _project_root() -> Path:
    # api/routes/auth/user_auth.py -> root is 3 parents up
    return Path(__file__).resolve().parents[3]


def _build_public_base_url(request: Request) -> str:
    env_base = (os.getenv("PUBLIC_BASE_URL") or "").strip()
    if env_base:
        return env_base.rstrip("/")
    return str(request.base_url).rstrip("/")


def _guess_extension(upload: UploadFile) -> str:
    name = (upload.filename or "").lower()
    if "." in name:
        ext = name.rsplit(".", 1)[-1]
        if ext and len(ext) <= 8:
            return f".{ext}"
    ct = (upload.content_type or "").lower()
    if ct == "image/jpeg":
        return ".jpg"
    if ct == "image/png":
        return ".png"
    if ct == "image/webp":
        return ".webp"
    return ""

# --- Models ---
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    full_name: str = None


class UpdateMePayload(BaseModel):
    full_name: str


class ChangePasswordPayload(BaseModel):
    old_password: str
    new_password: str

# --- API Đăng ký ---
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserRegister):
    # 1. Kiểm tra email đã tồn tại chưa
    if users.find_one({"email": user_data.email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email này đã được đăng ký"
        )

    # Validate password policy
    _enforce_password_policy(user_data.password)

    # 2. Mã hóa mật khẩu
    hashed_password = get_password_hash(user_data.password)

    # 3. Lưu vào MongoDB
    new_user = user_document(
        {
            "email": user_data.email,
            "password": hashed_password,  # Lưu mật khẩu đã mã hóa
            "full_name": user_data.full_name,
            "role": "user",
            "status": "active",
            "block": {"isBlocked": False},
        }
    )
    users.insert_one(new_user)

    return {"message": "Đăng ký thành công"}

# --- API Đăng nhập ---
@router.post("/login", response_model=TokenResponse)
async def login_user(login_data: UserLogin):
    # 1. Tìm user trong DB
    user = users.find_one({"email": login_data.email})
    
    # 2. Kiểm tra user tồn tại và mật khẩu đúng không
    if not user or not verify_password(login_data.password, user.get("password")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )

    # Enforce blocked users
    status_val = user.get("status") or "active"
    block = user.get("block") or {}
    is_blocked = bool(block.get("isBlocked")) or (status_val == "blocked")

    blocked_until = block.get("blockedUntil")
    if is_blocked and isinstance(blocked_until, datetime):
        now = now_utc()
        if blocked_until.tzinfo is None:
            blocked_until = blocked_until.replace(tzinfo=timezone.utc)
        if blocked_until <= now:
            users.update_one(
                {"_id": user.get("_id")},
                {"$set": {"status": "active", "block": {"isBlocked": False}, "updatedAt": now}},
            )
            is_blocked = False

    if is_blocked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is blocked")

    # Update last login
    users.update_one(
        {"_id": user.get("_id")},
        {"$set": {"lastLoginAt": now_utc(), "updatedAt": now_utc()}},
    )

    # 3. Tạo token (nhúng user_id để FE decode ra currentUser.id)
    access_token = create_access_token(data={"sub": user["email"], "user_id": str(user["_id"])})
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "full_name": user.get("full_name", "")
    }

@router.post("/logout")
def logout_user(current_email: str = Depends(get_current_user)):
    # JWT is stateless: real logout is typically handled by FE deleting the token.
    # If you want server-side revocation (blacklist), we can add it with MongoDB.
    return {"message": "Đăng xuất thành công", "email": current_email}


@router.get("/me")
def get_me(current_email: str = Depends(get_current_user)):
    u = users.find_one({"email": current_email})
    if not u:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return _user_to_me_response(u)


@router.patch("/me")
def update_me(payload: UpdateMePayload, current_email: str = Depends(get_current_user)):
    full_name = (payload.full_name or "").strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="full_name is required")

    res = users.update_one(
        {"email": current_email},
        {"$set": {"full_name": full_name, "updatedAt": now_utc()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    u = users.find_one({"email": current_email})
    return _user_to_me_response(u)


@router.post("/me/avatar")
async def upload_avatar(
    request: Request,
    avatar: UploadFile = File(...),
    current_email: str = Depends(get_current_user),
):
    u = users.find_one({"email": current_email})
    if not u:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    content_type = (avatar.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="avatar must be an image")

    # Prefer Cloudinary if configured (consistent with community image uploads)
    try:
        from api.utils.community import cloudinary_is_configured, cloudinary_init  # type: ignore
    except Exception:
        cloudinary_is_configured = lambda: False  # type: ignore
        cloudinary_init = lambda: None  # type: ignore

    avatar_url: Optional[str] = None

    if cloudinary_is_configured():
        cloudinary_init()
        try:
            from cloudinary import uploader  # type: ignore

            res = uploader.upload(
                avatar.file,
                folder="avatars",
                public_id=f"{str(u.get('_id'))}_{uuid4().hex}",
                resource_type="image",
            )
            avatar_url = res.get("secure_url") or res.get("url")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Cloudinary upload failed: {e}")
    else:
        uploads_dir = _project_root() / "uploads" / "avatars"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        ext = _guess_extension(avatar)
        filename = f"{str(u.get('_id'))}_{uuid4().hex}{ext}"
        dst = uploads_dir / filename

        # Limit to 10MB to avoid abuse
        max_bytes = 10 * 1024 * 1024
        total = 0
        try:
            with dst.open("wb") as f:
                while True:
                    chunk = await avatar.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise HTTPException(status_code=413, detail="avatar file too large")
                    f.write(chunk)
        finally:
            await avatar.close()

        base = _build_public_base_url(request)
        avatar_url = f"{base}/uploads/avatars/{filename}"

    users.update_one(
        {"email": current_email},
        {"$set": {"avatarUrl": avatar_url, "updatedAt": now_utc()}},
    )
    u2 = users.find_one({"email": current_email})
    return _user_to_me_response(u2)


@router.post("/me/change-password")
def change_password(payload: ChangePasswordPayload, current_email: str = Depends(get_current_user)):
    u = users.find_one({"email": current_email})
    if not u:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not verify_password(payload.old_password, u.get("password", "")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mật khẩu cũ không đúng")

    _enforce_password_policy(payload.new_password)
    new_hash = get_password_hash(payload.new_password)
    users.update_one(
        {"email": current_email},
        {"$set": {"password": new_hash, "updatedAt": now_utc()}},
    )
    return {"ok": True}