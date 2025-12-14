from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from database.mongo import admins
from core.security.security import create_access_token, verify_password, decode_admin_token

router = APIRouter(prefix="/admin", tags=["Admin"])
security = HTTPBearer()

class AdminLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return decode_admin_token(credentials.credentials)

@router.post("/login", response_model=TokenResponse)
def login_admin(payload: AdminLogin):
    admin = admins.find_one({"email": payload.email})
    if not admin:
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")

    if not verify_password(payload.password, admin.get("password", "")):
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")

    token = create_access_token({"sub": payload.email})
    return TokenResponse(access_token=token)

@router.get("/me")
def get_admin_me(current_email: str = Depends(get_current_admin)):
    return {"email": current_email}
