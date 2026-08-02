"""Health + readiness. Used by the deploy smoke test and deploy.ps1's activation check."""
from __future__ import annotations

import os
import time

from fastapi import APIRouter

from app import warmup
from app.config import get_settings
from app.services.datastore import get_store

router = APIRouter(tags=["health"])

# Process start, so `uptime_s` can answer "did the container restart?" from the outside.
# Without it, a restart and a merely-cold cache look identical to a caller — which is
# exactly the ambiguity that made the cold-start latency take measurement to diagnose.
_STARTED_AT = time.time()


@router.get("/health")
def health():
    settings = get_settings()
    store = get_store()
    cases_loaded = 0
    try:
        # Cheap once warm-up has run (it parses CaseMaster as its first step). Kept as-is
        # because deploy.ps1, deploy.sh and the UI's "N FIRs" badge all read this field.
        cases_loaded = len(store.rows("CaseMaster"))
    except NotImplementedError:
        pass
    state = warmup.status()
    return {
        "status": "ok",
        "data_mode": settings.data_mode,
        "llm_provider": settings.llm_provider,
        "cases_loaded": cases_loaded,
        # baked in at image build (deploy.ps1 --build-arg); proves which build is live
        "build_id": os.getenv("BUILD_ID", "dev"),
        "pid": os.getpid(),
        "uptime_s": round(time.time() - _STARTED_AT, 1),
        "warm": state["warm"],
        "warming": state["running"],
    }


@router.get("/warm")
def warm():
    """Fill every expensive cache and report per-step timings.

    This is what the keep-warm cron should hit — `/health` only ever touched one cache
    (CaseMaster) and left DBSCAN, IsolationForest, Louvain and the case view cold, so a
    container could be alive and still serve a 3.7s first request.

    Cheap to call repeatedly: once warm, every step is a cache hit and the whole thing
    returns in single-digit milliseconds. A cold run is ~5-8s — inside AppSail's 30s
    request cap and cron-job.org's 30s timeout, but keep an eye on `total_ms` if steps
    get added.
    """
    result = warmup.warm()
    return {
        "status": "ok",
        "build_id": os.getenv("BUILD_ID", "dev"),
        "uptime_s": round(time.time() - _STARTED_AT, 1),
        **result,
    }
