"""
KSP Crime Intelligence Platform — API.

Single FastAPI service, deployed to Catalyst AppSail (managed Python runtime).
Run locally:  uvicorn app.main:app --reload --port 9000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import warmup
from app.config import get_settings
from app.routers import (
    alerts,
    analytics,
    assistant,
    cases,
    health,
    hotspots,
    network,
    predictive,
    report,
)

settings = get_settings()

# gunicorn owns stdout on AppSail; without this the warm-up timings never reach the logs.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Warm the analytical caches at boot so the first visitor doesn't pay for them.

    Backgrounded on purpose — see warmup.warm_in_background() for why blocking startup is
    the wrong trade on AppSail.
    """
    warmup.warm_in_background()
    yield


app = FastAPI(
    title="KSP Crime Intelligence Platform API",
    version="0.1.0",
    description="Geospatial hotspots, network/link analysis, predictive AI, and NL query "
                "over Karnataka crime data. Serves precomputed aggregates (see CLAUDE.md).",
    lifespan=lifespan,
)

# On Catalyst the AppSail gateway already emits CORS headers; adding ours too duplicates
# Access-Control-Allow-Origin (browsers reject that). Gate it via APP_CORS_ENABLED.
if settings.app_cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# One router per pillar.
app.include_router(health.router)
app.include_router(cases.router)
app.include_router(hotspots.router)
app.include_router(network.router)
app.include_router(predictive.router)
app.include_router(assistant.router)
app.include_router(analytics.router)
app.include_router(alerts.router)
app.include_router(report.router)


@app.get("/")
def root():
    return {
        "service": "ksp-crime-platform",
        "version": app.version,
        "docs": "/docs",
        "data_mode": settings.data_mode,
    }
