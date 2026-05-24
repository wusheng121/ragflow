from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RAG 复习助手"
    app_env: str = "dev"
    database_url: str = "sqlite:///./ragflow.db"

    ragflow_enabled: bool = True
    ragflow_base_url: str = "http://127.0.0.1:9380"
    ragflow_api_key: str = "ragflow-9JJcnbpqPMfnVFAKDZPQd_O8pE_rzEicfq6L98-3RTo"
    ragflow_upload_path: str = "/api/v1/datasets/{dataset_id}/documents"
    ragflow_retrieve_path: str = "/api/v1/retrieval"
    ragflow_dataset_id: str = ""

    local_llm_enabled: bool = True
    local_llm_base_url: str = "https://dashscope.aliyuncs.com"
    local_llm_chat_path: str = "/compatible-mode/v1/chat/completions"
    local_llm_model: str = "qwen-plus"
    local_llm_api_key: str = "sk-95598cc26dcb4418a37e31ac7129c8d8"

    score_pass_line: int = 70

    jwt_secret_key: str = "arimakanaa"
    jwt_expire_minutes: int = 60 * 24 * 7

    model_config = SettingsConfigDict(env_file=".env", env_prefix="RAGFLOW_")


@lru_cache
def get_settings() -> Settings:
    return Settings()

