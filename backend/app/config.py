"""Central configuration via pydantic-settings — reads from .env automatically."""
from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Look for .env in the monorepo root (two levels up from this file: app/ → backend/ → root)
_ROOT = Path(__file__).parent.parent.parent
_ENV_FILE = _ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    # Provider: "anthropic" | "openai" | "gemini" | "stub"
    # Auto-falls back to "stub" if the chosen provider has no key set.
    llm_provider: str = "stub"

    # Paths (resolved relative to backend/ at runtime)
    database_url: str = "sqlite+aiosqlite:///./data/ehr.db"
    fhir_bundles_dir: Path = Path("./data/fhir_bundles")
    cache_dir: Path = Path("./data/cache")
    faiss_index_dir: Path = Path("./data/faiss_index")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Embedding dimension for all-MiniLM-L6-v2 / OpenAI fallback
    embedding_dim: int = 384


settings = Settings()
