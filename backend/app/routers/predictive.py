"""
Pillar 3 — predictive risk & anomaly.

Production: serve the precomputed `risk_scores` / `anomalies` tables (Zia AutoML +
anomaly job). Local mode returns a transparent heuristic risk score per district
(volume + heinous concentration + pendency + recent momentum), plus two genuine
scikit-learn signals layered on top: a KMeans unsupervised risk tier and IsolationForest
multivariate anomaly detection (see services/aggregations.py for why these — not a
fabricated supervised model — are the honest way to add real ML here).
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter

from app.services import aggregations, firdata, reference
from app.services.datastore import read_aggregate_or_compute

router = APIRouter(prefix="/api/predictive", tags=["predictive"])


@lru_cache(maxsize=1)
def _cached_multivariate_anomalies():
    """IsolationForest fit is real model-training work, not a cheap rollup — cache it
    per process lifetime, same trade-off as the DBSCAN cache in routers/hotspots.py."""
    return aggregations.multivariate_anomalies(firdata.cases())


def _compute_risk_scores():
    items = aggregations.district_stats(firdata.cases(), reference.socioeconomic())
    items = sorted(items, key=lambda x: x["risk_score"], reverse=True)
    ml_tier = aggregations.ml_risk_tiers(items)
    for it in items:
        it["ml_tier"] = ml_tier.get(it["district"])
    return items


@router.get("/risk-scores")
def risk_scores():
    items = read_aggregate_or_compute("risk_scores", _compute_risk_scores)
    return {"method": "heuristic risk_score: 30% volume + 20% per-capita rate (Census 2011) + "
                      "20% heinous share + 15% pendency + 15% 90-day momentum, ranked primary; "
                      "ml_tier: unsupervised KMeans clustering over the same feature set as a "
                      "genuine ML signal (no labeled outcomes exist to train a supervised model "
                      "on synthetic data honestly — Phase 3 swaps this for Zia AutoML once real "
                      "case-outcome labels exist)", "items": items}


def _compute_anomalies():
    items = aggregations.anomalies(firdata.cases()) + _cached_multivariate_anomalies()
    items.sort(key=lambda a: abs(a["z"]), reverse=True)
    return items


@router.get("/anomalies")
def anomalies():
    """Anomaly call-outs from two methods: transparent z-score outliers (univariate,
    per volume/hour signal) plus IsolationForest (genuine scikit-learn ML, multivariate —
    catches unusual *combinations* no single z-score would flag). Local mode derives both
    on the fly; production SELECTs the precomputed `anomalies` table the risk job wrote."""
    items = read_aggregate_or_compute("anomalies", _compute_anomalies)
    return {"method": "z-score outliers (volume & temporal) + IsolationForest "
                      "(multivariate, scikit-learn)", "count": len(items), "items": items}
