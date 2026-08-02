# Cold-start latency and the keep-warm cron

## The problem this solved

Opening the app after an idle period took >10 s. An immediate reload was instantaneous.

The first diagnosis was "AppSail scales the container to zero, so ping it" — and a
5-minute `/health` cron was set up on that basis. **It didn't fix anything**, because
scale-to-zero was not what was happening.

Measured live on 2026-08-02, *while that cron was running*:

| Probe | Result | What it means |
|---|---|---|
| `GET /health` | ~200 ms | container **alive** — no cold boot |
| first `GET /api/hotspots/cells` | **3,675 ms** | but its cache was **empty** |
| second `GET /api/hotspots/cells` | 209 ms | 17× faster |
| 15× `/health` back to back | flat 179–236 ms | one instance, no round-robin |

A live container serving a 3.7 s request is not a container-lifecycle problem. It is a
**process-cache** problem, and pinging harder was never going to fix it.

## Root cause

Three things compounded.

**1. Every expensive value lived in a per-process cache, populated only on demand.**
Fifteen of them across `services/firdata.py`, `services/datastore.py`,
`routers/hotspots.py`, `routers/predictive.py`, `services/mo.py`. Nothing survived a
restart and nothing was built until a request happened to need it.

**2. `/health` warmed exactly one of them.** It calls `len(store.rows("CaseMaster"))`,
which fills a single CSV's cache. It never touched `lookups()`, `parties()`, `arrests()`,
`cases()`, `offenders()`, `communities()`, DBSCAN, or IsolationForest. The cron kept the
container up and the analytics caches cold — which is precisely the state measured above.

**3. The cold cost was multiplied, not shared — this is where the >10 s came from.**
The Dashboard opens with 12 concurrent requests. FastAPI runs sync `def` handlers in a
threadpool, and **`functools.lru_cache` does not hold its lock across the wrapped call**,
so concurrent misses on the same key *each* execute the function. Ten-plus threads each
independently parsed 12 MB of CSV and rebuilt the same 20,000-row join, serialised by the
GIL onto a single worker.

Measured A/B locally, same machine, same data — 12 concurrent Dashboard requests against
a freshly started server:

| | wall clock |
|---|---|
| before | **49,638 ms** |
| after | **2,788 ms** |

A fourth issue surfaced while verifying: `district_stats()` was recomputed **per request**,
so `/api/predictive/risk-scores` and `/api/hotspots/districts` cost ~400 ms on every call
even fully warm. Now cached (`services/derived.py`):

| endpoint (warm, 3 consecutive calls) | before | after |
|---|---|---|
| `/api/predictive/risk-scores` | 428 / 465 / 430 ms | 31 / 16 / 15 ms |
| `/api/hotspots/districts` | 448 / 377 / 390 ms | 14 / 13 / 13 ms |
| `/api/predictive/anomalies` | 276 / 260 / 271 ms | 13 / 13 / 12 ms |

## The fix

- **`services/cache.py`** — `cached()`, a single-flight replacement for `lru_cache` that
  holds a *per-key* lock across the computation. Concurrent misses wait for the first
  caller instead of duplicating its work. This is what collapses the 12× multiplier.
- **`warmup.py` + a lifespan hook in `main.py`** — the process warms its own caches on a
  daemon thread at boot, so a restart self-heals in ~5–10 s with nobody pinging it.
  Backgrounded, not synchronous: AppSail health-checks during boot, and because the caches
  are single-flight a request landing mid-warm *waits on the in-flight computation* rather
  than starting its own.
- **`GET /warm`** — runs the same warm set and returns per-step timings.
- **`services/derived.py`** — cached whole-state aggregate views (`district_stats`,
  `anomalies`, `risk_scores`).

## The cron

**One job, pointed at `/warm`.** The startup hook covers restarts; the cron covers the
windows it can't — deploys and platform recycles.

Create it at <https://console.cron-job.org>:

- **URL** — `https://ksp-api-50043111658.development.catalystappsail.in/warm`
- **Schedule** — every 5 minutes
- **Method** — `GET`
- **Timeout** — raise to the maximum (30 s on the free tier). A cold `/warm` is ~5–10 s;
  once warm it returns in ~30 ms, so the steady-state cost is nil.
- **Notifications** — on failure only.

The old four-job setup (`/health` + three heavy endpoints) is obsolete — `/warm` covers
everything those did, and covers the caches they missed.

## Verifying it works

```powershell
$B = "https://ksp-api-50043111658.development.catalystappsail.in"
foreach ($p in "/health","/api/hotspots/cells","/api/predictive/risk-scores","/api/network/communities") {
  "{0,-34} {1,6:N0} ms" -f $p, (Measure-Command { curl.exe -s -o NUL "$B$p" }).TotalMilliseconds
}
curl.exe -s "$B/health"    # -> pid, uptime_s, warm, build_id
```

The real test: run it **after 30+ minutes of not touching the site**. All under ~500 ms
means it's working.

`/health` now reports `pid` and `uptime_s`, so "did the container restart?" is directly
answerable — the ambiguity that made this take measurement rather than log-reading to
diagnose. If `uptime_s` keeps resetting, the platform is recycling containers and the
startup warm-up is carrying the load; if it climbs steadily, the container is stable and
single-flight is what fixed it.

## Cost

Keeping the container alive bills the same as an always-on instance (~$0.08/GB-hr at 512 MB):

| Schedule | Per month | Over the ~60-day credit window |
|---|---|---|
| 24/7 | ~$29 | ~$58 of $250 |
| 08:30–23:30 IST | ~$17 | ~$34 of $250 |

To restrict: **Custom** schedule → every 5 minutes, hours `3`–`17` (jobs run in UTC;
03:00–17:59 UTC = 08:30–23:30 IST). The tradeoff is one cold start for the first visitor
each morning — now ~5–10 s of self-warming rather than a 50 s stampede. Widen to 24/7 the
day before a demo.

## Known gaps

Accepted, not oversights:

1. **Warm latency has a ~80–250 ms floor.** Network RTT to the Zoho India datacenter.
   Unavoidable without HTTP response caching.
2. **Every dashboard revisit refetches all 12 queries.** `frontend/src/main.tsx`
   constructs `new QueryClient()` with no defaults, so `staleTime: 0` and
   `refetchOnWindowFocus: true` — navigating away and back, or just alt-tabbing, re-fires
   everything. Cheap now that the server answers in ~15 ms, but still wasteful. A ~4-line
   fix, deliberately out of scope for this backend-only change.
3. **`/api/analytics/summary` stays ~80 ms**, the one endpoint still doing a real
   per-request pass over all 20,000 cases. Fast enough to leave alone.
4. **Warm-up takes ~10 s locally** (~5 s on the deployed box, which is faster at DBSCAN).
   Watch `total_ms` in the `/warm` response if steps get added — the budget is AppSail's
   30 s request cap.
