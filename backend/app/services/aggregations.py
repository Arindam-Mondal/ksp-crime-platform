"""
Pure aggregation functions over the denormalised case view (services/firdata.cases()).

The API request path calls these in local mode (DATA_MODE=local). The Catalyst
Cron/Event jobs use a mirrored copy in `functions/common/aggregations.py` to write
the same results into aggregate tables; in catalyst mode the API just SELECTs those.
Keep the two copies in sync.

Every function takes list[dict] case rows and returns plain dicts/lists so it
serialises straight to JSON.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta


# ------------------------------------------------------------------ ML gate ----
# Real (not heuristic) methods live behind lazy imports so the module still loads if
# scikit-learn is ever unavailable at runtime; scikit-learn is a hard requirement
# (requirements.txt) so this is a defensive fallback, not the expected path.

def _sk():
    from sklearn.cluster import DBSCAN, KMeans  # noqa: F401
    from sklearn.ensemble import IsolationForest  # noqa: F401
    from sklearn.preprocessing import StandardScaler  # noqa: F401
    import numpy as np  # noqa: F401
    return DBSCAN, KMeans, IsolationForest, StandardScaler, np


# ---------------------------------------------------------------- helpers ----
def _parse(dt: str) -> datetime | None:
    try:
        return datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _ref_now(cases: list[dict]) -> datetime:
    """Reference 'now' = latest incident timestamp (synthetic data ends ~today)."""
    latest = None
    for r in cases:
        d = _parse(r.get("incident", ""))
        if d and (latest is None or d > latest):
            latest = d
    return latest or datetime.now()


def district_centroids(cases: list[dict]) -> dict[str, tuple[float, float]]:
    acc: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for c in cases:
        if c.get("lat") is not None and c.get("lon") is not None:
            acc[c["district"]].append((c["lat"], c["lon"]))
    return {d: (sum(x[0] for x in pts) / len(pts), sum(x[1] for x in pts) / len(pts))
            for d, pts in acc.items() if pts}


def hotspot_clusters(cases: list[dict], eps_km: float = 1.5, min_samples: int = 6,
                      top: int = 500) -> list[dict]:
    """Density-based hotspot detection via DBSCAN over haversine distance.

    Replaces naive lat/lon grid-rounding with the DBSCAN method actually named in
    project_tech_stack.md / CLAUDE.md: points are clustered by real geographic density
    (eps_km radius, min_samples core-point threshold), and sparse/isolated cases are
    dropped as noise rather than counted as their own 1-case "hotspot" the way grid
    binning would. Falls back to grid-rounding only if scikit-learn is unavailable.
    Returns one row per cluster: centroid + member count, sorted densest-first — same
    shape the grid method returned, so callers/consumers don't need to change."""
    pts = [(c["lat"], c["lon"]) for c in cases if c.get("lat") is not None and c.get("lon") is not None]
    if len(pts) < min_samples:
        return []
    try:
        DBSCAN, _, _, _, np = _sk()
        coords = np.radians(np.array(pts))
        earth_radius_km = 6371.0088
        eps = eps_km / earth_radius_km
        labels = DBSCAN(eps=eps, min_samples=min_samples, metric="haversine",
                        algorithm="ball_tree").fit_predict(coords)
        clusters: dict[int, list[tuple[float, float]]] = defaultdict(list)
        for (lat, lon), label in zip(pts, labels):
            if label == -1:  # noise — not a real density cluster
                continue
            clusters[int(label)].append((lat, lon))
        out = [
            {"lat": round(sum(p[0] for p in members) / len(members), 5),
             "lon": round(sum(p[1] for p in members) / len(members), 5),
             "count": len(members)}
            for members in clusters.values()
        ]
        out.sort(key=lambda x: x["count"], reverse=True)
        return out[:top]
    except ImportError:  # pragma: no cover — scikit-learn is a hard dependency
        grid: dict[tuple, int] = defaultdict(int)
        for lat, lon in pts:
            grid[(round(lat, 2), round(lon, 2))] += 1
        out = [{"lat": lat, "lon": lon, "count": n} for (lat, lon), n in grid.items()]
        out.sort(key=lambda x: x["count"], reverse=True)
        return out[:top]


def pearson_r(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation coefficient. None if <3 paired points or zero variance."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    syy = sum((p[1] - my) ** 2 for p in pairs)
    if sxx <= 0 or syy <= 0:
        return None
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    return round(sxy / (sxx ** 0.5 * syy ** 0.5), 3)


# --------------------------------------------------- A: spike / trend alerts ----
def spike_alerts(cases: list[dict], min_recent: int = 8,
                 ratio_threshold: float = 2.0) -> list[dict]:
    """Per (district, crime sub-head): last-30-day volume vs historical monthly baseline."""
    ref = _ref_now(cases)
    window_start = ref - timedelta(days=30)
    centroids = district_centroids(cases)

    groups: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    for c in cases:
        d = _parse(c.get("incident", ""))
        if d:
            groups[(c.get("district", ""), c.get("sub_head", ""))].append(d)

    alerts = []
    for (district, sub_head), dates in groups.items():
        recent = sum(1 for d in dates if d > window_start)
        if recent < min_recent:
            continue
        hist_months: Counter = Counter()
        for d in dates:
            if d <= window_start:
                hist_months[d.strftime("%Y-%m")] += 1
        if len(hist_months) < 2:
            continue
        counts = list(hist_months.values())
        baseline = sum(counts) / len(counts)
        if baseline <= 0:
            continue
        ratio = recent / baseline
        std = statistics.pstdev(counts) or 1.0
        z = (recent - baseline) / std
        if ratio < ratio_threshold:
            continue
        lat, lon = centroids.get(district, (None, None))
        alerts.append({
            "district": district,
            "sub_head": sub_head,
            "recent": recent,
            "baseline": round(baseline, 1),
            "ratio": round(ratio, 2),
            "z": round(z, 2),
            "severity": "Critical" if ratio >= 3 else "Elevated",
            "lat": lat,
            "lon": lon,
            "last_seen": max(dates).strftime("%Y-%m-%d"),
        })
    alerts.sort(key=lambda a: a["ratio"], reverse=True)
    return alerts


# ------------------------------------------------------ B: anomaly detection ----
def anomalies(cases: list[dict], top_n: int = 12) -> list[dict]:
    """Transparent statistical outliers: district monthly-volume spikes + rare-hour crimes."""
    out: list[dict] = []

    # (1) district monthly-volume z-scores
    by_district_month: dict[str, Counter] = defaultdict(Counter)
    for c in cases:
        d = _parse(c.get("incident", ""))
        if d:
            by_district_month[c.get("district", "")][d.strftime("%Y-%m")] += 1
    for district, months in by_district_month.items():
        series = list(months.values())
        if len(series) < 6:
            continue
        mean = sum(series) / len(series)
        std = statistics.pstdev(series) or 1.0
        for month, n in months.items():
            z = (n - mean) / std
            if z >= 2.5 and n >= mean + 5:
                out.append({
                    "kind": "volume",
                    "subject": district,
                    "period": month,
                    "observed": n,
                    "expected": round(mean, 1),
                    "z": round(z, 2),
                    "severity": "High" if z >= 3.2 else "Medium",
                    # `description` is the English rendering and stays authoritative —
                    # services/report.py feeds it to the LLM as grounding context, where
                    # English is correct. `template`/`params` let the UI re-render the
                    # same sentence in the reader's language without the language ever
                    # becoming a cache key on this precomputed aggregate.
                    "template": "anomaly.volume",
                    "params": {"district": district, "n": n, "month": month,
                               "z": f"{z:.1f}", "mean": f"{mean:.0f}"},
                    "description": f"{district} registered {n} cases in {month} — "
                                   f"{z:.1f}σ above its {mean:.0f}/month norm.",
                })

    # (2) crimes at a rare hour for their sub-head
    by_sub_hour: dict[str, Counter] = defaultdict(Counter)
    for c in cases:
        if c.get("hour") is not None:
            by_sub_hour[c.get("sub_head", "")][c["hour"]] += 1
    for sub, hours in by_sub_hour.items():
        total = sum(hours.values())
        if total < 50:
            continue
        for hour, n in hours.items():
            p = n / total
            if p < 0.012 and n >= 3:
                out.append({
                    "kind": "temporal",
                    "subject": sub,
                    "period": f"{hour:02d}:00",
                    "observed": n,
                    "expected": round(total / 24, 1),
                    "z": round((p - 1 / 24) / (1 / 24), 2),
                    "severity": "Medium",
                    "template": "anomaly.temporal",
                    "params": {"n": n, "sub_head": sub, "hour": f"{hour:02d}:00",
                               "pct": f"{p*100:.1f}"},
                    "description": f"{n} {sub} cases at {hour:02d}:00 — an unusual hour "
                                   f"for this crime ({p*100:.1f}% of its cases).",
                })

    out.sort(key=lambda a: abs(a["z"]), reverse=True)
    return out[:top_n]


def multivariate_anomalies(cases: list[dict], contamination: float = 0.08,
                            top_n: int = 8) -> list[dict]:
    """Genuine ML anomaly detection: IsolationForest over district-month feature
    vectors (volume, heinous share, chargesheet rate, pendency).

    Complements the z-score checks above, which are univariate (one signal at a time).
    IsolationForest catches multivariate outliers — a district-month whose *combination*
    of signals is unusual even if no single signal crosses a z-score threshold on its
    own. This is a trained scikit-learn ensemble model, not a hand-tuned formula."""
    by_dm: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in cases:
        d = _parse(c.get("incident", ""))
        if d and c.get("district"):
            by_dm[(c["district"], d.strftime("%Y-%m"))].append(c)

    keys, rows = [], []
    for (district, month), recs in by_dm.items():
        n = len(recs)
        if n < 5:
            continue
        heinous_share = sum(1 for r in recs if r.get("heinous")) / n
        finals = [r for r in recs if r.get("cstype")]
        cs_rate = sum(1 for r in finals if r["cstype"] == "A") / len(finals) if finals else 0.0
        pendency = sum(1 for r in recs if r.get("status_id") == 1) / n
        keys.append((district, month, n, heinous_share, cs_rate, pendency))
        rows.append([n, heinous_share, cs_rate, pendency])

    if len(rows) < 20:
        return []

    try:
        _, _, IsolationForest, _, np = _sk()
        X = np.array(rows, dtype=float)
        model = IsolationForest(n_estimators=200, contamination=contamination, random_state=42)
        pred = model.fit_predict(X)
        scores = model.score_samples(X)  # lower (more negative) = more anomalous
        cutoff = float(np.percentile(scores, 8))
    except ImportError:  # pragma: no cover — scikit-learn is a hard dependency
        return []

    out = []
    for (district, month, n, heinous_share, cs_rate, pendency), label, score in zip(keys, pred, scores):
        if label != -1:
            continue
        out.append({
            "kind": "multivariate",
            "subject": district,
            "period": month,
            "observed": n,
            "expected": None,
            "z": round(float(-score), 3),
            "severity": "High" if score <= cutoff else "Medium",
            "template": "anomaly.multivariate",
            "params": {"district": district, "month": month, "n": n,
                       "heinous": f"{heinous_share*100:.0f}", "cs": f"{cs_rate*100:.0f}",
                       "pendency": f"{pendency*100:.0f}"},
            "description": f"{district} in {month}: an unusual combination of volume "
                            f"({n}), heinous share ({heinous_share*100:.0f}%), chargesheet "
                            f"rate ({cs_rate*100:.0f}%) and pendency ({pendency*100:.0f}%) — "
                            f"flagged by IsolationForest across every district-month, not "
                            f"any single threshold.",
            "method": "isolation_forest",
        })
    out.sort(key=lambda a: a["z"], reverse=True)
    return out[:top_n]


# ------------------------------------------ D: district stats + drill-down ----
def district_stats(cases: list[dict], socio: dict[str, dict] | None = None) -> list[dict]:
    """Per-district rollup: volume, per-capita rate, heinous share, chargesheet rate,
    pendency, risk.

    When `socio` (district -> {population, ...}) is supplied, each district also gets a
    per-100k crime rate and the risk score folds in a per-capita term, so a genuinely
    high-crime district is no longer confused with a merely populous one. Districts with
    no population row fall back to using their volume rank as the per-capita proxy, so
    the score stays coherent across the whole table (see reference.socioeconomic())."""
    socio = socio or {}
    ref = _ref_now(cases)
    recent_cut = ref - timedelta(days=90)
    by_d: dict[str, list[dict]] = defaultdict(list)
    for c in cases:
        if c.get("district"):
            by_d[c["district"]].append(c)
    max_count = max((len(v) for v in by_d.values()), default=1)
    centroids = district_centroids(cases)

    # First pass: per-district facts + per-100k rate (where population is known).
    facts: dict[str, dict] = {}
    for district, rows in by_d.items():
        n = len(rows)
        pop = socio.get(district, {}).get("population")
        per_100k = round(n / pop * 100_000, 1) if pop else None
        facts[district] = {"rows": rows, "n": n, "per_100k": per_100k}
    max_per_100k = max((f["per_100k"] for f in facts.values() if f["per_100k"]), default=0) or 1

    items = []
    for district, f in facts.items():
        rows, n = f["rows"], f["n"]
        heinous = sum(1 for c in rows if c.get("heinous"))
        finals = [c for c in rows if c.get("cstype")]
        charged = sum(1 for c in finals if c["cstype"] == "A")
        open_n = sum(1 for c in rows if c.get("status_id") == 1)
        recent = sum(1 for c in rows
                     if (_parse(c.get("incident", "")) or ref) > recent_cut)
        heinous_share = heinous / n if n else 0
        cs_rate = charged / len(finals) if finals else 0
        pendency = open_n / n if n else 0
        volume_norm = n / max_count
        # per-capita term: real rate where population is known, else fall back to volume.
        per_capita_norm = f["per_100k"] / max_per_100k if f["per_100k"] else volume_norm
        # risk: volume + per-capita rate + heinous concentration + pendency + recent momentum
        risk = round(0.30 * volume_norm + 0.20 * per_capita_norm + 0.20 * heinous_share
                     + 0.15 * pendency + 0.15 * min(1.0, recent / max(1, n * 0.2)), 3)
        lat, lon = centroids.get(district, (None, None))
        items.append({
            "district": district,
            "cases": n,
            "per_100k": f["per_100k"],
            "heinous_share": round(heinous_share * 100, 1),
            "chargesheet_rate": round(cs_rate * 100, 1),
            "pendency_rate": round(pendency * 100, 1),
            "recent_90d": recent,
            "risk_score": risk,
            "lat": lat,
            "lon": lon,
        })
    items.sort(key=lambda x: x["cases"], reverse=True)
    return items


def ml_risk_tiers(items: list[dict], k: int = 3) -> dict[str, str]:
    """Unsupervised risk tiering via KMeans, as a genuine ML complement to the
    transparent heuristic risk_score above.

    There's no labeled "this district was actually high-risk" ground truth in a
    synthetic dataset, so a supervised model here would be fabricated, not real ML —
    KMeans clustering on the same multivariate feature set is the honest unsupervised
    alternative: districts are grouped by the natural structure in their crime profile
    rather than a hand-weighted sum. Tiers are ranked by mean heuristic risk_score
    within each cluster so "High" still means what a reader expects."""
    if len(items) < k:
        return {}
    try:
        _, KMeans, _, StandardScaler, np = _sk()
    except ImportError:  # pragma: no cover — scikit-learn is a hard dependency
        return {}

    feats = np.array([
        [it["cases"], it.get("per_100k") or 0, it["heinous_share"], it["pendency_rate"], it["recent_90d"]]
        for it in items
    ], dtype=float)
    X = StandardScaler().fit_transform(feats)
    labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(X)

    cluster_mean_risk = {}
    for cluster in set(labels):
        idx = [i for i, c in enumerate(labels) if c == cluster]
        cluster_mean_risk[cluster] = sum(items[i]["risk_score"] for i in idx) / len(idx)
    ranked = sorted(cluster_mean_risk, key=lambda c: cluster_mean_risk[c], reverse=True)
    tier_names = ["High", "Medium", "Low"] if k == 3 else [f"Tier {i + 1}" for i in range(k)]
    rank_of = {cluster: i for i, cluster in enumerate(ranked)}

    return {
        items[i]["district"]: tier_names[rank_of[cluster]] if rank_of[cluster] < len(tier_names) else f"Tier {rank_of[cluster] + 1}"
        for i, cluster in enumerate(labels)
    }


def socioeconomic_correlation(cases: list[dict], socio: dict[str, dict]) -> dict:
    """Correlate district crime rate against urbanisation, literacy and population
    density — the 'why behind the where'. Only districts with a socio-economic row are
    included; returns per-district rows plus Pearson r for each indicator."""
    counts: Counter = Counter(c["district"] for c in cases if c.get("district"))
    items = []
    for district, s in socio.items():
        n = counts.get(district, 0)
        pop = s.get("population")
        if not pop:
            continue
        items.append({
            "district": district,
            "cases": n,
            "per_100k": round(n / pop * 100_000, 1),
            "population": pop,
            "urban_pct": s.get("urban_pct"),
            "literacy_pct": s.get("literacy_pct"),
            "pop_density": s.get("pop_density"),
        })
    items.sort(key=lambda x: x["per_100k"], reverse=True)

    rates = [i["per_100k"] for i in items]
    correlations = {
        "urbanization": pearson_r([i["urban_pct"] for i in items], rates),
        "literacy": pearson_r([i["literacy_pct"] for i in items], rates),
        "density": pearson_r([i["pop_density"] for i in items], rates),
    }
    return {
        "items": items,
        "correlations": correlations,
        "method": "crime rate = cases / population × 100,000 (Census 2011 population); "
                   "Pearson r vs urbanisation %, literacy %, and population density.",
    }


def station_breakdown(cases: list[dict], district: str) -> dict:
    """Drill-down for one district: per-station counts, top sub-heads, hourly profile.

    Station coordinates are the centroid of that station's case locations (the ERD's
    Unit table carries no coordinates)."""
    rows = [c for c in cases if c.get("district") == district]
    by_station: dict[str, list[dict]] = defaultdict(list)
    for c in rows:
        by_station[c.get("station", "")].append(c)
    stations = []
    for s, cs_rows in sorted(by_station.items(), key=lambda kv: -len(kv[1])):
        pts = [(c["lat"], c["lon"]) for c in cs_rows
               if c.get("lat") is not None and c.get("lon") is not None]
        lat = sum(p[0] for p in pts) / len(pts) if pts else None
        lon = sum(p[1] for p in pts) / len(pts) if pts else None
        heinous = sum(1 for c in cs_rows if c.get("heinous"))
        stations.append({"station": s, "cases": len(cs_rows),
                         "heinous": heinous, "lat": lat, "lon": lon})
    by_type = [{"name": k, "count": n}
               for k, n in Counter(c.get("sub_head", "") for c in rows).most_common()]
    hours = Counter(c["hour"] for c in rows if c.get("hour") is not None)
    by_hour = [{"hour": h, "count": hours.get(h, 0)} for h in range(24)]
    return {
        "district": district,
        "total": len(rows),
        "stations": stations,
        "by_type": by_type,
        "by_hour": by_hour,
    }
