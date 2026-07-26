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
    # QuickML LLM Serving chat endpoint (GLM-4.7-Flash — Qwen 2.5-14B was deprecated,
    # migration cutover 2026-07-31) auths with just two headers, confirmed from the
    # console's own "Sample Request and Response" tab:
    # Authorization: Zoho-oauthtoken <token> + CATALYST-ORG. No endpoint key, no Environment
    # header for this endpoint type (that was the older custom-pipeline-endpoint contract).
    llm_provider: str = "mock"
    quickml_endpoint: str = ""          # Full chat URL from the endpoint's details page
                                         # (project id is baked into the path, e.g.
                                         # https://api.catalyst.zoho.in/quickml/v1/project/<id>/glm/chat)
    # NOTE: named quickml_org_id (env QUICKML_ORG_ID), NOT catalyst_org_id/CATALYST_ORG_ID —
    # the AppSail console rejects CATALYST_ORG_ID as a reserved key (Catalyst auto-injects
    # its own env vars with that name pattern). Same value goes in the CATALYST-ORG header.
    quickml_org_id: str = ""
    quickml_model: str = "crm-di-glm47b_30b_it"  # model id shown in the console's sample payload
    # Auth — preferred: refresh-token trio (auto-renews hourly access tokens forever).
    # From api-console.zoho.com Self Client: Generate Code (scope QuickML.deployment.READ)
    # -> exchange once for access_token + refresh_token -> the refresh_token never expires.
    # https://www.zoho.com/accounts/protocol/oauth/self-client/authorization-code-flow.html
    quickml_client_id: str = ""         # Self Client -> Client Secret tab
    quickml_client_secret: str = ""     # Self Client -> Client Secret tab
    quickml_refresh_token: str = ""     # from the one-time authorization_code exchange (never expires)
    quickml_accounts_url: str = "https://accounts.zoho.in/oauth/v2/token"  # India DC; see /oauth/serverinfo for others
    # Fallback: a directly-pasted access token (Zoho-oauthtoken). Expires in 1hr — only
    # useful for a quick manual test; the refresh-token trio above is what should run live.
    quickml_oauth_token: str = ""

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
