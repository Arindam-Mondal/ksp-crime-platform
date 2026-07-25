"""
Pillar 3 — predictive risk & anomaly.

Production: serve the precomputed `risk_scores` / `anomalies` tables (Zia AutoML +
anomaly job). Local mode returns a transparent heuristic risk score per district
(volume + heinous concentration + pendency + recent momentum) so the dashboard renders.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.services import aggregations, firdata, reference

router = APIRouter(prefix="/api/predictive", tags=["predictive"])


@router.get("/risk-scores")
def risk_scores():
    items = aggregations.district_stats(firdata.cases(), reference.socioeconomic())
    items = sorted(items, key=lambda x: x["risk_score"], reverse=True)
    return {"method": "heuristic: 30% volume + 20% per-capita rate (Census 2011) + 20% "
                      "heinous share + 15% pendency + 15% 90-day momentum "
                      "(Phase 3 replaces with Zia AutoML)", "items": items}


@router.get("/anomalies")
def anomalies():
    """Statistical anomaly call-outs. Local mode derives them on the fly; production
    serves the precomputed `anomalies` table written by the risk job."""
    items = aggregations.anomalies(firdata.cases())
    return {"method": "z-score outliers (volume & temporal)", "count": len(items), "items": items}
