"""
Pillar 1 — geospatial hotspots & trends.

NOTE: in production these endpoints SELECT the precomputed `hotspot_cells` /
`district_stats` / `alerts` tables written by the Cron jobs (Phase 1). For the
Phase 0 scaffold we derive lightweight aggregates from the CSV so the map has data.
Keep this cheap — anything heavy belongs in functions/.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter

from app.services import aggregations
from app.services.datastore import get_store

router = APIRouter(prefix="/api/hotspots", tags=["hotspots"])


@router.get("/by-district")
def by_district():
    rows = get_store().rows("incidents")
    counts = Counter(r["district"] for r in rows)
    return {"items": [{"district": d, "incidents": n} for d, n in counts.most_common()]}


@router.get("/cells")
def cells(precision: int = 2):
    """Crude grid aggregation (round lat/lon) -> hotspot cells with counts."""
    rows = get_store().rows("incidents")
    grid: dict[tuple, int] = defaultdict(int)
    for r in rows:
        try:
            key = (round(float(r["lat"]), precision), round(float(r["lon"]), precision))
        except (ValueError, KeyError):
            continue
        grid[key] += 1
    cells = [{"lat": lat, "lon": lon, "count": c} for (lat, lon), c in grid.items()]
    cells.sort(key=lambda x: x["count"], reverse=True)
    return {"precision": precision, "items": cells[:500]}


@router.get("/districts")
def districts():
    """Per-district choropleth metrics (incidents, SEI, risk, centroid)."""
    store = get_store()
    items = aggregations.district_stats(store.rows("incidents"), store.rows("locations"))
    return {"items": items}


@router.get("/stations")
def stations(district: str):
    """District drill-down: station counts, top crime types, hourly profile."""
    store = get_store()
    return aggregations.station_breakdown(store.rows("incidents"), store.rows("locations"), district)


@router.get("/by-hour")
def by_hour(crime_type: str | None = None):
    """Time-of-day distribution (drives the spatiotemporal view)."""
    rows = get_store().rows("incidents")
    hours = Counter()
    for r in rows:
        if crime_type and r.get("crime_type") != crime_type:
            continue
        try:
            hours[int(r["datetime"][11:13])] += 1
        except (ValueError, KeyError, IndexError):
            continue
    return {"items": [{"hour": h, "count": hours.get(h, 0)} for h in range(24)]}
