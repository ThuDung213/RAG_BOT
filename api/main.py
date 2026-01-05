from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from api.routes.ask import router as ask_router
from api.routes.auth.admin_auth import router as admin_auth_router
from api.routes.auth.user_auth import router as user_auth_router
from api.routes.admin.community import router as admin_community_router
from api.routes.admin.users import router as admin_users_router
from api.routes.community import router as community_router
from database.mongo import init_indexes
from api.routes.gallery import router as gallery_router
from api.routes.admin.locations import router as create_location
from api.routes.admin.gallery import router as admin_gallery_router
from api.routes.locations import router as locations_router
import uvicorn

app = FastAPI(title="Danang History Agent API")

ROOT_DIR = Path(__file__).resolve().parents[1]
UPLOADS_DIR = ROOT_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

origins = [
    "http://localhost:5173", 
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # Cho phép các nguồn gốc này
    allow_credentials=True,
    allow_methods=["*"],              # RẤT QUAN TRỌNG: Cho phép tất cả phương thức, bao gồm OPTIONS
    allow_headers=["*"],              # Cho phép tất cả các Header (bao gồm Content-Type)
)

app.include_router(create_location)
app.include_router(locations_router)
app.include_router(gallery_router)
app.include_router(admin_gallery_router)
app.include_router(ask_router)
app.include_router(admin_auth_router)
app.include_router(user_auth_router)
app.include_router(admin_community_router)
app.include_router(admin_users_router)
app.include_router(community_router)


@app.on_event("startup")
def _startup_init_indexes() -> None:
    # Create required MongoDB indexes (idempotent) and fail fast if DB is unreachable.
    init_indexes()

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",   
        port=8000,         
        workers=4,           # 4 processes
        loop="asyncio",      # Event loop
        access_log=False,    # Tắt log để tăng tốc
        timeout_keep_alive=5 # Giảm timeout
    )