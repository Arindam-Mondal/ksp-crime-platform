"""
Emerging-trend spike alerts (challenge cap #1 — "red-zone pulsing").

Local mode derives alerts on the fly from incidents. In production the `hotspot_job`
Cron function writes the `alerts` / `trend_baselines` tables and this just SELECTs them.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.services import aggregations
from app.services.datastore import get_store

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/spikes")
def spikes():
    store = get_store()
    items = aggregations.spike_alerts(store.rows("incidents"), store.rows("locations"))
    return {"count": len(items), "items": items}
