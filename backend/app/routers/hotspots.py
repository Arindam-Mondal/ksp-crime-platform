"""
Pillar 1 — geospatial hotspots & trends over CaseMaster latitude/longitude.

NOTE: in production these endpoints SELECT the precomputed `hotspot_cells` /
`district_stats` / `alerts` tables written by the Cron jobs. For local mode we derive
lightweight aggregates from the case view. Keep this cheap — anything heavy belongs
in functions/.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter

from app.services import aggregations, firdata, reference

router = APIRouter(prefix="/api/hotspots", tags=["hotspots"])


@router.get("/by-district")
def by_district():
    counts = Counter(r["district"] for r in firdata.cases() if r["district"])
    return {"items": [{"district": d, "cases": n} for d, n in counts.most_common()]}


@router.get("/cells")
def cells(precision: int = 2, sub_head: str | None = None):
    """Crude grid aggregation (round lat/lon) -> hotspot cells with counts."""
    grid: dict[tuple, int] = defaultdict(int)
    for r in firdata.cases():
        if sub_head and r["sub_head"] != sub_head:
            continue
        if r["lat"] is None or r["lon"] is None:
            continue
        grid[(round(r["lat"], precision), round(r["lon"], precision))] += 1
    out = [{"lat": lat, "lon": lon, "count": c} for (lat, lon), c in grid.items()]
    out.sort(key=lambda x: x["count"], reverse=True)
    return {"precision": precision, "items": out[:500]}


@router.get("/districts")
def districts():
    """Per-district choropleth metrics (volume, per-capita rate, heinous share,
    chargesheet rate, pendency, risk, centroid)."""
    return {"items": aggregations.district_stats(firdata.cases(), reference.socioeconomic())}


@router.get("/stations")
def stations(district: str):
    """District drill-down: per-station counts, top sub-heads, hourly profile."""
    return aggregations.station_breakdown(firdata.cases(), district)


@router.get("/by-hour")
def by_hour(sub_head: str | None = None):
    """Time-of-day distribution (drives the spatiotemporal view)."""
    hours = Counter()
    for r in firdata.cases():
        if sub_head and r["sub_head"] != sub_head:
            continue
        if r["hour"] is not None:
            hours[r["hour"]] += 1
    return {"items": [{"hour": h, "count": hours.get(h, 0)} for h in range(24)]}
