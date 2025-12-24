from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from database.mongo import admins
from core.security.security import create_access_token, verify_password, decode_admin_token

router = APIRouter(prefix="/admin", tags=["Admin"])
security = HTTPBearer(auto_error=False)

class AdminLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

def get_current_admin(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    """Validate admin token + admin role.

    Returns the admin document for downstream handlers.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    email = decode_admin_token(credentials.credentials)
    admin = admins.find_one({"email": email})
    if not admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if (admin.get("role") or "admin") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return admin

@router.post("/login", response_model=TokenResponse)
def login_admin(payload: AdminLogin):
    admin = admins.find_one({"email": payload.email})
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không đúng")

    if not verify_password(payload.password, admin.get("password", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không đúng")

    if (admin.get("role") or "admin") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    token = create_access_token({"sub": payload.email})
    return TokenResponse(access_token=token)

@router.get("/me")
def get_admin_me(current_admin: dict = Depends(get_current_admin)):
    return {"id": str(current_admin.get("_id")), "email": current_admin.get("email")}
