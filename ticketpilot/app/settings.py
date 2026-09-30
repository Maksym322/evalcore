"""Environment-driven configuration (TechDesign §3.5). Secrets come from env only."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime knobs. Reads a local ``.env`` if present; env vars override."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Connection (SQLAlchemy async URL). Default keeps the app importable offline.
    database_url: str = "postgresql+asyncpg://localhost/ticketpilot"

    # Retrieval / pipeline knobs.
    active_strategy: str = "fixed_512_50"
    active_embed_model: str = "gemini-embedding-2"
    top_k: int = 5
    conf_threshold: float = 0.6
    rrf_threshold: float = 0.01  # min fused RRF score before retrieval is deemed too weak (§3.2)
    llm_model: str = "gemini-3.5-flash-lite"

    # Secrets (names only; values live in .env or the platform secret store).
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    anthropic_api_key: str | None = None
    github_token: str | None = None
    api_token: str | None = None
    eval_token: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton for app/runtime use."""
    return Settings()
