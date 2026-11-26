"""Application settings loaded from environment / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root (gym-bro/) so .env works whether cwd is backend/ or repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    groq_api_key: str = ""
    # Prefer Qwen on Groq for structured JSON; gpt-oss often emits native tool calls
    groq_model: str = "qwen/qwen3.8-27b"
    groq_fast_model: str = "qwen/qwen3.8-27b"
    # Optional: enables full Cognis hybrid embeddings; without it we use local Groq memory
    gemini_api_key: str = ""
    jwt_secret: str = Field(default="dev-only-change-me")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    database_url: str = "sqlite:///./data/gymbro.db"
    memory_data_dir: str = "./data/memory"

    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    chat_rate_limit_per_minute: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key.strip())

    def resolve_sqlite_path(self) -> Path | None:
        """Return filesystem path for sqlite URLs so we can mkdir parent."""
        url = self.database_url
        if not url.startswith("sqlite:///"):
            return None
        raw = url.removeprefix("sqlite:///")
        path = Path(raw)
        if not path.is_absolute():
            path = Path.cwd() / path
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
