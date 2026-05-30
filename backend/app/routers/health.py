"""Health + readiness. Used by the Phase 0 deploy smoke test."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.services.datastore import get_store

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    settings = get_settings()
    store = get_store()
    # In local mode, report whether the synthetic data is present.
    incidents_loaded = 0
    try:
        incidents_loaded = len(store.rows("incidents"))
    except NotImplementedError:
        pass
    return {
        "status": "ok",
        "data_mode": settings.data_mode,
        "llm_provider": settings.llm_provider,
        "incidents_loaded": incidents_loaded,
    }
