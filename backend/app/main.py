"""
KSP Crime Intelligence Platform — API.

Single FastAPI service, deployed to Catalyst AppSail (managed Python runtime).
Run locally:  uvicorn app.main:app --reload --port 9000
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import analytics, assistant, health, hotspots, incidents, network, predictive

settings = get_settings()

app = FastAPI(
    title="KSP Crime Intelligence Platform API",
    version="0.1.0",
    description="Geospatial hotspots, network/link analysis, predictive AI, and NL query "
                "over Karnataka crime data. Serves precomputed aggregates (see CLAUDE.md).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# One router per pillar.
app.include_router(health.router)
app.include_router(incidents.router)
app.include_router(hotspots.router)
app.include_router(network.router)
app.include_router(predictive.router)
app.include_router(assistant.router)
app.include_router(analytics.router)


@app.get("/")
def root():
    return {
        "service": "ksp-crime-platform",
        "version": app.version,
        "docs": "/docs",
        "data_mode": settings.data_mode,
    }
