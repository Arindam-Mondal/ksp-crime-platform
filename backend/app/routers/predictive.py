"""
Pillar 3 — predictive risk & anomaly.

Production: serve the precomputed `risk_scores` / `anomalies` tables (Zia AutoML +
anomaly job, Phase 3). Phase 0 scaffold returns a transparent heuristic risk score
(recent volume x inverse socio-economic index) so the dashboard renders.
"""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter

from app.services.datastore import get_store

router = APIRouter(prefix="/api/predictive", tags=["predictive"])


@router.get("/risk-scores")
def risk_scores():
    incidents = get_store().rows("incidents")
    locations = get_store().rows("locations")
    counts = Counter(r["district"] for r in incidents)
    # average socio-economic index per district
    sei: dict[str, list[float]] = {}
    for l in locations:
        try:
            sei.setdefault(l["district"], []).append(float(l["socio_economic_index"]))
        except (ValueError, KeyError):
            continue
    max_count = max(counts.values()) if counts else 1
    items = []
    for district, n in counts.items():
        vals = sei.get(district, [0.5])
        avg_sei = sum(vals) / max(1, len(vals))
        # higher volume + lower socio-economic index -> higher heuristic risk
        score = round(0.7 * (n / max_count) + 0.3 * (1 - avg_sei), 3)
        items.append({"district": district, "incidents": n,
                      "socio_economic_index": round(avg_sei, 3), "risk_score": score})
    items.sort(key=lambda x: x["risk_score"], reverse=True)
    return {"method": "heuristic-placeholder (Phase 3 replaces with Zia AutoML)", "items": items}
