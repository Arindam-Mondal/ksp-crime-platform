"""Health + readiness. Used by the deploy smoke test and deploy.ps1's activation check."""
from __future__ import annotations

import os

from fastapi import APIRouter

from app.config import get_settings
from app.services.datastore import get_store

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    settings = get_settings()
    store = get_store()
    cases_loaded = 0
    try:
        cases_loaded = len(store.rows("CaseMaster"))
    except NotImplementedError:
        pass
    return {
        "status": "ok",
        "data_mode": settings.data_mode,
        "llm_provider": settings.llm_provider,
        "cases_loaded": cases_loaded,
        # baked in at image build (deploy.ps1 --build-arg); proves which build is live
        "build_id": os.getenv("BUILD_ID", "dev"),
    }
