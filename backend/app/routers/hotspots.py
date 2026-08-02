"""
Pillar 1 — geospatial hotspots & trends over CaseMaster latitude/longitude.

NOTE: in production these endpoints SELECT the precomputed `hotspot_cells` /
`district_stats` / `alerts` tables written by the Cron jobs. For local mode we derive
lightweight aggregates from the case view. Keep this cheap — anything heavy belongs
in functions/.
"""
from __future__ import annotations

from collections import Counter
from fastapi import APIRouter

from app.services import aggregations, derived, firdata
from app.services.cache import cached
from app.services.datastore import read_aggregate_or_compute

router = APIRouter(prefix="/api/hotspots", tags=["hotspots"])


@router.get("/by-district")
def by_district():
    counts = Counter(r["district"] for r in firdata.cases() if r["district"])
    return {"items": [{"district": d, "cases": n} for d, n in counts.most_common()]}


@cached(maxsize=32)
def _cached_clusters(sub_head: str | None, eps_km: float, min_samples: int):
    """DBSCAN is real clustering work (not a cheap dict rollup) — cache per parameter
    combo so it only runs once per process, same trade-off as firdata's @cached views.
    `firdata.cases()` is itself cached and constant for the process lifetime in local
    mode, so caching on (sub_head, eps_km, min_samples) alone is safe.

    Stays bounded at 32: eps_km/min_samples come straight off the query string, so an
    unbounded cache here would be caller-controlled memory growth."""
    rows = firdata.cases()
    if sub_head:
        rows = [r for r in rows if r["sub_head"] == sub_head]
    return aggregations.hotspot_clusters(rows, eps_km=eps_km, min_samples=min_samples)


@router.get("/cells")
def cells(sub_head: str | None = None, eps_km: float = 1.5, min_samples: int = 6):
    """DBSCAN density clusters (haversine) -> hotspot cells with counts.

    Real spatial clustering, not grid-rounding: dense areas are kept as clusters,
    isolated/sparse points are dropped as noise rather than each counted as their own
    "hotspot" the way a naive grid would.

    In catalyst mode this reads the `hotspot_cells` table the nightly job already
    wrote (state-wide, default params) instead of recomputing — but a `sub_head`
    filter or non-default eps/min_samples always needs a live recompute, since the
    precomputed table only covers the state-wide default slice."""
    if sub_head or eps_km != 1.5 or min_samples != 6:
        items = _cached_clusters(sub_head, eps_km, min_samples)
    else:
        items = read_aggregate_or_compute("hotspot_cells", lambda: _cached_clusters(None, 1.5, 6))
    return {"method": f"DBSCAN (haversine, eps={eps_km}km, min_samples={min_samples})", "items": items}


@router.get("/districts")
def districts():
    """Per-district choropleth metrics (volume, per-capita rate, heinous share,
    chargesheet rate, pendency, risk, centroid)."""
    items = read_aggregate_or_compute("district_stats", derived.district_stats)
    return {"items": items}


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
