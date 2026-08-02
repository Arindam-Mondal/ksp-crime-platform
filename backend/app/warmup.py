"""
Cold-start warm-up.

Every expensive value in this app lives in a per-process cache (services/cache.py), so a
freshly started container serves its first visitor at ~10s while it parses 12 MB of CSV,
joins 20,000 cases, and fits DBSCAN / IsolationForest / Louvain. Nothing pre-populates
those caches; historically the first *user* paid for all of it.

This module pays that cost on a background thread at boot instead (see app/main.py), and
exposes the same routine at `GET /warm` for the keep-warm cron to hit after a deploy or a
platform recycle — the two windows a startup hook can't cover.

Pinging `/health` does not do this job. It touches exactly one cache (CaseMaster rows)
and leaves the other fifteen empty, which is why a 5-minute `/health` cron kept the
container alive while `/api/hotspots/cells` still took 3.7s.

Steps run in dependency order — cheap shared foundations first, so each later step finds
its inputs already built rather than rebuilding them.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

log = logging.getLogger("ksp.warmup")

_lock = threading.Lock()
_state: dict[str, Any] = {"warm": False, "running": False, "steps": [], "total_ms": None}


def _steps() -> list[tuple[str, Callable[[], Any]]]:
    """Imported lazily: routers import services, main imports routers, and warm-up is
    triggered from main — a module-level import here would close that cycle."""
    from app.routers.hotspots import _cached_clusters
    from app.routers.predictive import _cached_multivariate_anomalies
    from app.services import derived, firdata, mo

    return [
        # Foundations — the CSV parse + ERD joins nearly every endpoint depends on.
        ("lookups", firdata.lookups),
        ("sections_by_case", firdata.sections_by_case),
        ("parties", firdata.parties),
        ("arrests", firdata.arrests),
        ("chargesheets_by_case", firdata.chargesheets_by_case),
        ("cases", firdata.cases),
        ("case_index", firdata.case_index),
        # Network pillar.
        ("offenders", firdata.offenders),
        ("co_accused_adjacency", firdata.co_accused_adjacency),
        ("communities", firdata.communities),          # Louvain
        ("mo_signatures", mo._repeat_signatures),
        # Hotspots pillar — default slice only; other params recompute on demand.
        ("hotspot_clusters", lambda: _cached_clusters(None, 1.5, 6)),   # DBSCAN
        ("district_stats", derived.district_stats),
        ("district_stats_no_socio", lambda: derived.district_stats(with_socio=False)),
        # Predictive pillar.
        ("anomalies", derived.anomalies),                               # z-score outliers
        ("multivariate_anomalies", _cached_multivariate_anomalies),     # IsolationForest
        ("risk_scores", derived.risk_scores),                           # KMeans tiers
    ]


def warm() -> dict[str, Any]:
    """Fill every expensive cache. Idempotent — each step is a cache fill, so a second
    call is a no-op costing microseconds. Safe to call concurrently: `cached` collapses
    duplicate work, so a request arriving mid-warm waits on the in-flight computation
    rather than starting its own.

    A failing step is logged and skipped, never raised: a broken IsolationForest must not
    stop `cases()` from being warmed, and must not take the process down at boot.
    """
    started = time.perf_counter()
    with _lock:
        _state["running"] = True

    steps: list[dict[str, Any]] = []
    for name, fn in _steps():
        t0 = time.perf_counter()
        try:
            fn()
            ms = round((time.perf_counter() - t0) * 1000, 1)
            steps.append({"step": name, "ms": ms})
            log.info("warm %-24s %8.1f ms", name, ms)
        except Exception as exc:                      # noqa: BLE001 - warm-up is best-effort
            ms = round((time.perf_counter() - t0) * 1000, 1)
            steps.append({"step": name, "ms": ms, "error": str(exc)})
            log.warning("warm %-24s FAILED after %.1f ms: %s", name, ms, exc)

    total = round((time.perf_counter() - started) * 1000, 1)
    with _lock:
        _state.update(warm=True, running=False, steps=steps, total_ms=total)
    log.info("warm-up complete in %.1f ms (%d steps)", total, len(steps))
    return {"total_ms": total, "steps": steps}


def warm_in_background() -> threading.Thread:
    """Start warm-up off the startup path.

    Deliberately not synchronous: AppSail health-checks the container while it boots, and
    blocking startup for ~5s risks being marked unhealthy. Because the caches are
    single-flight, a request that lands mid-warm blocks on the same computation the warm
    thread is already running — it never duplicates it — so backgrounding costs nothing
    in correctness.
    """
    thread = threading.Thread(target=warm, name="ksp-warmup", daemon=True)
    thread.start()
    return thread


def status() -> dict[str, Any]:
    """Warm-up state for /health and /warm."""
    with _lock:
        return dict(_state)
