from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from database.mongo import users
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

# --- API Đăng ký ---
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserRegister):
    # 1. Kiểm tra email đã tồn tại chưa
    if users.find_one({"email": user_data.email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email này đã được đăng ký"
        )

    # 2. Mã hóa mật khẩu
    hashed_password = get_password_hash(user_data.password)

    # 3. Lưu vào MongoDB
    new_user = {
        "email": user_data.email,
        "password": hashed_password, # Lưu mật khẩu đã mã hóa
        "full_name": user_data.full_name,
        "role": "user"
    }
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