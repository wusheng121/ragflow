from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app import models  # noqa: F401
from app.api.v1 import assistant, attempts, materials, mistakes, subjects, users
from app.config import get_settings
from app.database import Base, engine
from app.web.pages import router as web_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=307)


app.include_router(materials.router, prefix="/api/v1")
app.include_router(assistant.router, prefix="/api/v1")
app.include_router(mistakes.router, prefix="/api/v1")
app.include_router(attempts.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(subjects.router, prefix="/api/v1")
app.include_router(web_router)

# Serve static front-end assets (css/js/img/pages)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


def _ensure_sqlite_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    table_columns = {
        "course_materials": {col["name"] for col in inspector.get_columns("course_materials")},
        "flashcards": {col["name"] for col in inspector.get_columns("flashcards")},
        "practice_attempts": {col["name"] for col in inspector.get_columns("practice_attempts")},
        "mistake_notes": {col["name"] for col in inspector.get_columns("mistake_notes")},
        "user_profiles": {col["name"] for col in inspector.get_columns("user_profiles")},
    }

    statements: list[str] = []
    if "user_id" not in table_columns["course_materials"]:
        statements.append("ALTER TABLE course_materials ADD COLUMN user_id INTEGER")
    if "subject_id" not in table_columns["course_materials"]:
        statements.append("ALTER TABLE course_materials ADD COLUMN subject_id INTEGER")
    if "user_id" not in table_columns["flashcards"]:
        statements.append("ALTER TABLE flashcards ADD COLUMN user_id INTEGER")
    if "user_id" not in table_columns["practice_attempts"]:
        statements.append("ALTER TABLE practice_attempts ADD COLUMN user_id INTEGER")
    if "user_id" not in table_columns["mistake_notes"]:
        statements.append("ALTER TABLE mistake_notes ADD COLUMN user_id INTEGER")
    if "assistant_correction" not in table_columns["mistake_notes"]:
        statements.append("ALTER TABLE mistake_notes ADD COLUMN assistant_correction TEXT")
    if "email" not in table_columns["user_profiles"]:
        statements.append("ALTER TABLE user_profiles ADD COLUMN email VARCHAR(200)")
    if "password_hash" not in table_columns["user_profiles"]:
        statements.append("ALTER TABLE user_profiles ADD COLUMN password_hash VARCHAR(255) DEFAULT ''")
    if "is_active" not in table_columns["user_profiles"]:
        statements.append("ALTER TABLE user_profiles ADD COLUMN is_active BOOLEAN DEFAULT 1")
    if "last_login_at" not in table_columns["user_profiles"]:
        statements.append("ALTER TABLE user_profiles ADD COLUMN last_login_at DATETIME")

    if statements:
        with engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))


