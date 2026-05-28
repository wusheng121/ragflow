from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RAG 复习助手"
    app_env: str = "dev"
    database_url: str = "sqlite:///./ragflow.db"

    ragflow_enabled: bool = True
    ragflow_base_url: str = ""
    ragflow_api_key: str = ""
    ragflow_upload_path: str = "/api/v1/datasets/{dataset_id}/documents"
    ragflow_retrieve_path: str = "/api/v1/retrieval"
    ragflow_dataset_id: str = ""

    local_llm_enabled: bool = True
    local_llm_base_url: str = ""
    local_llm_chat_path: str = "/compatible-mode/v1/chat/completions"
    local_llm_model: str = ""
    local_llm_api_key: str = ""

    score_pass_line: int = 70

    jwt_secret_key: str = ""
    jwt_expire_minutes: int = 60 * 24 * 7

    model_config = SettingsConfigDict(env_file=".env", env_prefix="RAGFLOW_")


@lru_cache
def get_settings() -> Settings:
    return Settings()

