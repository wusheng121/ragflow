from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "mysql+pymysql://root:password@127.0.0.1:3306/ragflow_review?charset=utf8mb4"
    upload_dir: str = "uploads"
    ragflow_api_url: str = "https://a221-240c-c603-1005-a4a9-3c87-6bb4-a3fb-bcd8.ngrok-free.app/"
    ragflow_api_key: str = "ragflow-PSWNQln8ui7ktqGJqZCkEROH7PIpuN8MeZK8wvRlKsc"
    ragflow_chat_id: str = ""
    ragflow_parse_timeout: int = 300
    ragflow_parse_poll_interval: int = 3
    serve_frontend: bool = True
    frontend_dir: str = ".."
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:8000,http://127.0.0.1:8000"
    jwt_secret: str = "change-me-in-production-ragflow-review"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    @property
    def upload_path(self) -> Path:
        path = BACKEND_ROOT / self.upload_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def frontend_path(self) -> Path:
        path = (BACKEND_ROOT / self.frontend_dir).resolve()
        return path

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ragflow_enabled(self) -> bool:
        return bool(self.ragflow_api_url and self.ragflow_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
