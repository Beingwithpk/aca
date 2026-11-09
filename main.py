import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.db import init_tables, close_pool
from src.routes.auth import router as auth_router
from src.routes.courses import router as courses_router
from src.routes.documents import router as documents_router
from src.routes.chat import router as chat_router
from src.routes.attendance import router as attendance_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure schema and extension existence
    try:
        init_tables()
    except Exception as e:
        print(f"[STARTUP WARNING] Database verification error: {e}")
    yield
    # Shutdown: cleanly shut down thread pools
    close_pool()


app = FastAPI(
    title="Academic RAG Core API",
    description="Backend API for Academic RAG, Attendance Roster, and Course Document Pipeline",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth_router)
app.include_router(courses_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(attendance_router)

# Ensure static directory exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "status": "online",
        "message": "Academic RAG Core API is active. Open /docs for Swagger UI."
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}