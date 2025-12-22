from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from api.routes.ask import router as ask_router
from api.routes.auth.admin_auth import router as admin_auth_router
from api.routes.auth.user_auth import router as user_auth_router
from api.routes.community import router as community_router
from api.routes.admin.locations import router as create_location
import uvicorn

app = FastAPI(title="Danang History Agent API")

origins = [
    "http://localhost:5173", 
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # Cho phép các nguồn gốc này
    allow_credentials=True,
    allow_methods=["*"],              # RẤT QUAN TRỌNG: Cho phép tất cả phương thức, bao gồm OPTIONS
    allow_headers=["*"],              # Cho phép tất cả các Header (bao gồm Content-Type)
)

app.include_router(create_location)
app.include_router(ask_router)
app.include_router(admin_auth_router)
app.include_router(user_auth_router)
app.include_router(community_router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",   
        port=8000,         
        workers=4,           # 4 processes
        loop="asyncio",      # Event loop
        access_log=False,    # Tắt log để tăng tốc
        timeout_keep_alive=5 # Giảm timeout
    )