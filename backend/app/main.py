from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.routers import auth, chat, health, history, knowledge_cards, practice, stats, subjects, wrong_book

settings = get_settings()
STATIC_DIR = settings.frontend_path

app = FastAPI(title="RAGFlow Review Assistant API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(subjects.router, prefix="/api")
app.include_router(knowledge_cards.router, prefix="/api")
app.include_router(practice.router, prefix="/api")
app.include_router(wrong_book.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(stats.router, prefix="/api")

if settings.serve_frontend and STATIC_DIR.is_dir():
    css_dir = STATIC_DIR / "css"
    js_dir = STATIC_DIR / "js"
    if css_dir.is_dir():
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if js_dir.is_dir():
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

    @app.get("/")
    def login_page():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/index.html")
    def login_page_alias():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/app.html")
    def app_page():
        return FileResponse(STATIC_DIR / "app.html")


@app.on_event("startup")
def on_startup():
    init_db()
