"""
Unit tests for the two capability gaps added on top of the FIR ERD:
  * socio-economic correlation + per-capita risk (aggregations)
  * Modus Operandi signature + similarity (mo)

Pure-function focused; a couple of endpoint smoke tests exercise the wired routers
against the bundled synthetic data.
"""
from __future__ import annotations

import math

from fastapi.testclient import TestClient

from app.main import app
from app.services import aggregations as agg
from app.services import mo
from app.services import reference


# ------------------------------------------------------------------ pearson_r ----
def test_pearson_perfect_positive():
    assert agg.pearson_r([1, 2, 3, 4], [2, 4, 6, 8]) == 1.0


def test_pearson_perfect_negative():
    assert agg.pearson_r([1, 2, 3, 4], [8, 6, 4, 2]) == -1.0


def test_pearson_too_few_points_is_none():
    assert agg.pearson_r([1, 2], [1, 2]) is None


def test_pearson_zero_variance_is_none():
    assert agg.pearson_r([5, 5, 5, 5], [1, 2, 3, 4]) is None


def test_pearson_skips_unpaired_nones():
    # None pairs are dropped; remaining 3 points are perfectly correlated.
    assert agg.pearson_r([1, 2, 3, None], [2, 4, 6, 100]) == 1.0


# ------------------------------------------------- district_stats per-capita ----
def _cases(district, n, pop_note=None):
    return [{"district": district, "incident": "2026-01-01 10:00:00", "hour": 10,
             "heinous": False, "cstype": "", "status_id": 1, "sub_head": "Theft",
             "sections": [], "lat": None, "lon": None} for _ in range(n)]


def test_district_stats_per_capita_rate():
    socio = {"Small": {"population": 100_000}, "Big": {"population": 10_000_000}}
    # Small: 50 cases / 100k = 50 per 100k ; Big: 50 cases / 10M = 0.5 per 100k
    rows = _cases("Small", 50) + _cases("Big", 50)
    stats = {s["district"]: s for s in agg.district_stats(rows, socio)}
    assert stats["Small"]["per_100k"] == 50.0
    assert stats["Big"]["per_100k"] == 0.5
    # Same volume, but the tiny-population district must carry the higher risk.
    assert stats["Small"]["risk_score"] > stats["Big"]["risk_score"]


def test_district_stats_without_socio_has_none_rate():
    rows = _cases("Nowhere", 10)
    s = agg.district_stats(rows, socio=None)[0]
    assert s["per_100k"] is None
    assert 0.0 <= s["risk_score"] <= 1.0


def test_socioeconomic_correlation_shape():
    socio = {
        "A": {"population": 100_000, "urban_pct": 90, "literacy_pct": 80, "pop_density": 5000},
        "B": {"population": 100_000, "urban_pct": 60, "literacy_pct": 75, "pop_density": 2000},
        "C": {"population": 100_000, "urban_pct": 30, "literacy_pct": 70, "pop_density": 500},
    }
    rows = _cases("A", 90) + _cases("B", 60) + _cases("C", 30)
    out = agg.socioeconomic_correlation(rows, socio)
    assert [i["district"] for i in out["items"]] == ["A", "B", "C"]  # rate-sorted
    # crime rate rises with urbanisation here -> strong positive r
    assert out["correlations"]["urbanization"] == 1.0


# ---------------------------------------------------------------- MO helpers ----
def test_cosine_identical_vectors():
    from collections import Counter
    v = Counter({"Theft": 3, "Burglary": 1})
    assert math.isclose(mo._cosine(v, v), 1.0)


def test_cosine_orthogonal_vectors():
    from collections import Counter
    assert mo._cosine(Counter({"Theft": 1}), Counter({"Murder": 1})) == 0.0


def test_jaccard():
    assert mo._jaccard({"a", "b"}, {"b", "c"}) == 1 / 3
    assert mo._jaccard(set(), set()) == 0.0


def test_time_bucket():
    assert mo._bucket(2) == "Night"
    assert mo._bucket(9) == "Morning"
    assert mo._bucket(15) == "Afternoon"
    assert mo._bucket(21) == "Evening"
    assert mo._bucket(None) is None


def test_similarity_bounds():
    a = {"crimes": __import__("collections").Counter({"Theft": 2}),
         "times": __import__("collections").Counter({"Night": 2}),
         "sections": {"IPC 379"}}
    assert mo.similarity(a, a) == 1.0


# ------------------------------------------------------------ reference data ----
def test_reference_has_karnataka_districts():
    socio = reference.socioeconomic()
    assert "Bengaluru City" in socio
    assert socio["Bengaluru City"]["population"] > 0
    assert socio["Bengaluru City"]["pop_density"] > 0
    assert len(socio) >= 30


# --------------------------------------------------------- endpoint smoke tests ----
client = TestClient(app)


def test_socioeconomic_endpoint():
    r = client.get("/api/analytics/socioeconomic")
    assert r.status_code == 200
    d = r.json()
    assert d["items"] and "correlations" in d
    top = d["items"][0]
    assert {"per_100k", "rate_rank", "volume_rank", "rank_shift"} <= set(top)


def test_risk_scores_has_per_capita():
    r = client.get("/api/predictive/risk-scores")
    assert r.status_code == 200
    assert "per_100k" in r.json()["items"][0]


def test_mo_endpoint():
    top = client.get("/api/network/top-offenders?limit=1").json()["items"][0]
    r = client.get(f"/api/network/mo/{top['person_id']}")
    assert r.status_code == 200
    d = r.json()
    assert "signature" in d and "matches" in d
    assert d["signature"]["n_cases"] >= 2


def test_mo_unknown_person_404():
    assert client.get("/api/network/mo/O99999999").status_code == 404
