"""
Cached whole-state aggregate views.

`services/aggregations.py` holds pure functions that take `cases` and return rollups —
correct, testable, and completely uncached. Several routers were calling them per request
over the full 20,000-case view, so `/api/predictive/risk-scores` and
`/api/hotspots/districts` cost ~400 ms *every* call, warm or cold, forever. (Measured on
a fully-warmed server: three consecutive calls at 428 / 465 / 430 ms, versus 17 ms for
`/api/hotspots/cells`, whose equivalent work is cached.)

This module is the cached layer between the two: zero-argument, whole-state, single-flight
views of the aggregations that more than one caller wants. Scope-filtered rollups (a single
district's stats in services/report.py) stay uncached — their inputs vary per request.

**Callers must treat the returned lists and dicts as read-only.** They are the cached
objects themselves, not copies; mutating one corrupts every later reader. `risk_scores()`
below is the worked example — it needs to add a field, so it copies first.
"""
from __future__ import annotations

from app.services import aggregations, firdata, reference
from app.services.cache import cached


@cached()
def district_stats(with_socio: bool = True) -> list[dict]:
    """Per-district metrics. `with_socio=False` is the variant the NL assistant and
    report builder use (no Census join), cached separately from the choropleth's."""
    socio = reference.socioeconomic() if with_socio else None
    return aggregations.district_stats(firdata.cases(), socio)


@cached()
def anomalies() -> list[dict]:
    """Univariate z-score outliers over the full case view."""
    return aggregations.anomalies(firdata.cases())


@cached()
def risk_scores() -> list[dict]:
    """District risk ranking + the unsupervised KMeans tier.

    Copies each row before adding `ml_tier`: these dicts are the same objects
    `district_stats()` hands to /api/hotspots/districts, and annotating them in place
    would leak an ml_tier field into that endpoint's response.
    """
    ranked = sorted(district_stats(), key=lambda x: x["risk_score"], reverse=True)
    tiers = aggregations.ml_risk_tiers(ranked)
    return [dict(row, ml_tier=tiers.get(row["district"])) for row in ranked]
