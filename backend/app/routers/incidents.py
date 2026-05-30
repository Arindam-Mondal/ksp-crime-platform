"""Incident + location lookups. Paginated to respect the 300-rows-per-query rule."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.datastore import get_store

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

PAGE_MAX = 300  # Catalyst Data Store hard cap.


@router.get("")
def list_incidents(
    district: str | None = None,
    crime_type: str | None = None,
    limit: int = Query(100, le=PAGE_MAX),
    offset: int = 0,
):
    rows = get_store().rows("incidents")
    if district:
        rows = [r for r in rows if r.get("district") == district]
    if crime_type:
        rows = [r for r in rows if r.get("crime_type") == crime_type]
    total = len(rows)
    return {"total": total, "limit": limit, "offset": offset,
            "items": rows[offset:offset + limit]}


@router.get("/locations")
def list_locations():
    """Station-level locations (small table) used to draw the base map."""
    return {"items": get_store().rows("locations")}


@router.get("/meta")
def meta():
    """Distinct districts and crime types for filter dropdowns."""
    rows = get_store().rows("incidents")
    districts = sorted({r["district"] for r in rows}) if rows else []
    crime_types = sorted({r["crime_type"] for r in rows}) if rows else []
    return {"districts": districts, "crime_types": crime_types}
