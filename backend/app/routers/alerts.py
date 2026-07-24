"""
Emerging-trend spike alerts (challenge cap #1 — "red-zone pulsing").

Local mode derives alerts on the fly from the case view. In production the
`hotspot_job` Cron function writes the `alerts` / `trend_baselines` tables and this
just SELECTs them.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.services import aggregations, firdata

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/spikes")
def spikes():
    items = aggregations.spike_alerts(firdata.cases())
    return {"count": len(items), "items": items}
