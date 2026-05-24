from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import get_settings

router = APIRouter(tags=["web"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _base_context(request: Request, *, active_page: str = "", body_class: str = "app-shell", show_topbar: bool = True) -> dict:
    settings = get_settings()
    return {
        "request": request,
        "active_page": active_page,
        "body_class": body_class,
        "show_topbar": show_topbar,
        "app_name": settings.app_name,
        "ragflow_enabled": settings.ragflow_enabled,
        "local_llm_enabled": settings.local_llm_enabled,
    }



@router.get("/login", include_in_schema=False)
def login_page(request: Request):
    return templates.TemplateResponse("pages/login.html", _base_context(request, active_page="login", body_class="auth-page", show_topbar=False))


@router.get("/register", include_in_schema=False)
def register_page(request: Request):
    return templates.TemplateResponse("pages/register.html", _base_context(request, active_page="register", body_class="auth-page", show_topbar=False))


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse("frontend_index.html", _base_context(request, active_page="dashboard"))


@router.get("/materials", response_class=HTMLResponse)
def materials_page(request: Request):
    return templates.TemplateResponse("pages/materials.html", _base_context(request, active_page="materials"))


@router.get("/flashcards", response_class=HTMLResponse)
def flashcards_page(request: Request):
    return templates.TemplateResponse("pages/flashcards.html", _base_context(request, active_page="flashcards"))


@router.get("/practice", response_class=HTMLResponse)
def practice_page(request: Request):
    return templates.TemplateResponse("pages/practice.html", _base_context(request, active_page="practice"))


@router.get("/mistakes", response_class=HTMLResponse)
def mistakes_page(request: Request):
    return templates.TemplateResponse("pages/mistakes.html", _base_context(request, active_page="mistakes"))


@router.get("/history", response_class=HTMLResponse)
def history_page(request: Request):
    return templates.TemplateResponse("pages/history.html", _base_context(request, active_page="history"))

