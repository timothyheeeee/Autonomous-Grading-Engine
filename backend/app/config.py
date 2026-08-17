from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Autonomous Group Assignment System"
    environment: str = "development"
    secret_key: str = "dev-secret-key-rotate-in-production"
    access_token_expire_minutes: int = 480
    algorithm: str = "HS256"

    database_url: str = f"sqlite:///{BACKEND_ROOT / 'data' / 'app.db'}"
    redis_url: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    vision_model: str = "gpt-4o"

    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "group-assignment-pipeline"

    max_graph_tokens: int = 50_000
    max_vision_failures: int = 2
    max_context_tokens: int = 4_000

    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def traces_dir(self) -> Path:
        path = BACKEND_ROOT / "data" / "traces"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def logs_dir(self) -> Path:
        path = BACKEND_ROOT / "data" / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
