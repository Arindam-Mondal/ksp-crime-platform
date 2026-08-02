"""
Tests for services/derived.py — the cached whole-state aggregate views.

Two things to hold down:
  * they are actually cached (the bug was ~400 ms of recomputation on every request to
    /api/predictive/risk-scores and /api/hotspots/districts, warm or cold);
  * callers share the cached objects, so a view that annotates rows must copy first.
    risk_scores() adds `ml_tier` to rows that district_stats() also hands to
    /api/hotspots/districts — in-place, that field would leak into the other endpoint's
    response and accumulate across requests.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services import derived

client = TestClient(app)


def test_district_stats_is_cached():
    a = derived.district_stats()
    b = derived.district_stats()
    assert a is b, "district_stats recomputed — the per-request cost is back"


def test_district_stats_socio_variants_are_cached_separately():
    with_socio = derived.district_stats()
    without = derived.district_stats(with_socio=False)
    assert with_socio is not without
    assert derived.district_stats(with_socio=False) is without
    # the Census join is the whole difference between them
    assert any(d["per_100k"] is not None for d in with_socio)
    assert all(d["per_100k"] is None for d in without)


def test_anomalies_is_cached():
    assert derived.anomalies() is derived.anomalies()


def test_risk_scores_does_not_mutate_district_stats():
    """The regression this guards: risk_scores() used to add ml_tier in place."""
    ranked = derived.risk_scores()
    assert all("ml_tier" in r for r in ranked)
    assert all("ml_tier" not in d for d in derived.district_stats()), \
        "ml_tier leaked into the shared district_stats rows"


def test_risk_scores_stable_across_calls():
    first = [dict(r) for r in derived.risk_scores()]
    second = derived.risk_scores()
    assert first == [dict(r) for r in second]


def test_risk_scores_ranked_descending():
    scores = [r["risk_score"] for r in derived.risk_scores()]
    assert scores == sorted(scores, reverse=True)


# ------------------------------------------------------------------- endpoints ----
def test_districts_endpoint_has_no_ml_tier():
    items = client.get("/api/hotspots/districts").json()["items"]
    assert items
    assert all("ml_tier" not in d for d in items)


def test_risk_scores_endpoint_has_ml_tier():
    items = client.get("/api/predictive/risk-scores").json()["items"]
    assert items
    assert all("ml_tier" in d for d in items)


def test_repeated_requests_do_not_accumulate_fields():
    """Shared cached rows + per-request annotation would grow the payload over time."""
    first = client.get("/api/hotspots/districts").json()["items"][0]
    for _ in range(3):
        client.get("/api/predictive/risk-scores")
    after = client.get("/api/hotspots/districts").json()["items"][0]
    assert set(first) == set(after)
