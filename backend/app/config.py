"""Application settings, loaded from environment / .env (see .env.example)."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "local" -> read data/output/*.csv ; "catalyst" -> use the Data Store SDK.
    data_mode: str = "local"
    # Default points at the repo's data/output relative to backend/.
    data_dir: str = os.path.join("..", "data", "output")

    # Catalyst
    catalyst_project_id: str = ""
    catalyst_environment: str = "development"

    # LLM gate (see services/llm.py). "mock" spends no credits.
    llm_provider: str = "mock"
    quickml_endpoint: str = ""
    quickml_api_key: str = ""
    quickml_model: str = "qwen2.5-14b-instruct"

    # Report PDF export (catalyst mode → SmartBrowz HTML→PDF stored in Stratus).
    # Empty = local mode: the API returns JSON and the frontend prints to PDF.
    smartbrowz_endpoint: str = ""
    smartbrowz_api_key: str = ""
    stratus_bucket: str = ""

    # CORS: local dev (Vite default port) + the deployed Catalyst Web Client origin.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://ksp-crime-platform-60072978366.development.catalystserverless.in",
    ]
    # On Catalyst, the AppSail gateway injects its own CORS headers; adding ours too produces
    # DUPLICATE Access-Control-Allow-Origin headers, which browsers reject. So disable the
    # app-level CORS middleware on Catalyst (set APP_CORS_ENABLED=false) and let the gateway
    # own CORS. Locally it defaults to True (harmless; dev uses the Vite proxy anyway).
    app_cors_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
