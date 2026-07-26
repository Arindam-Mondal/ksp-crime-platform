"""
Pure aggregation functions for the Catalyst Cron/Event jobs (superset mirror of
`backend/app/services/aggregations.py`, operating on the denormalised case view built
by `common/firview.py` from the ERD tables). Framework-free; takes list[dict] rows and
returns plain rows ready to UPSERT into the Data Store aggregate tables.

Keep the spike/anomaly/district functions in sync with the backend copy. The extra
functions here (hotspot_cells, graph_edges, risk_scores, trend_baselines) are what the
jobs precompute so the API request path can just SELECT them in catalyst mode.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta


def _parse(dt: str):
    try:
        return datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _ref_now(cases):
    latest = None
    for r in cases:
        d = _parse(r.get("incident", ""))
        if d and (latest is None or d > latest):
            latest = d
    return latest or datetime.now()


def _sk():
    """Lazy import of the real (non-heuristic) ML methods — scikit-learn is a hard
    requirement (requirements.txt) so this is a defensive fallback, not the expected path."""
    from sklearn.cluster import DBSCAN, KMeans  # noqa: F401
    from sklearn.ensemble import IsolationForest  # noqa: F401
    from sklearn.preprocessing import StandardScaler  # noqa: F401
    import numpy as np  # noqa: F401
    return DBSCAN, KMeans, IsolationForest, StandardScaler, np


def district_centroids(cases):
    acc = defaultdict(list)
    for c in cases:
        if c.get("lat") is not None and c.get("lon") is not None:
            acc[c["district"]].append((c["lat"], c["lon"]))
    return {d: (sum(x[0] for x in pts) / len(pts), sum(x[1] for x in pts) / len(pts))
            for d, pts in acc.items() if pts}


def pearson_r(xs, ys):
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


# ---------------------------------------------------------- hotspot_cells ----
def hotspot_cells(cases, eps_km: float = 1.5, min_samples: int = 6, top: int = 500):
    """DBSCAN density clusters (haversine) — see backend/app/services/aggregations.py
    for the full rationale. Keep in sync with that copy."""
    pts = [(c["lat"], c["lon"]) for c in cases if c.get("lat") is not None and c.get("lon") is not None]
    if len(pts) < min_samples:
        return []
    try:
        DBSCAN, _, _, _, np = _sk()
        coords = np.radians(np.array(pts))
        eps = eps_km / 6371.0088
        labels = DBSCAN(eps=eps, min_samples=min_samples, metric="haversine",
                        algorithm="ball_tree").fit_predict(coords)
        clusters = defaultdict(list)
        for (lat, lon), label in zip(pts, labels):
            if label == -1:
                continue
            clusters[int(label)].append((lat, lon))
        cells = [
            {"lat": round(sum(p[0] for p in m) / len(m), 5),
             "lon": round(sum(p[1] for p in m) / len(m), 5),
             "count": len(m)}
            for m in clusters.values()
        ]
    except ImportError:  # pragma: no cover — scikit-learn is a hard dependency
        grid = defaultdict(int)
        for lat, lon in pts:
            grid[(round(lat, 2), round(lon, 2))] += 1
        cells = [{"lat": lat, "lon": lon, "count": n} for (lat, lon), n in grid.items()]
    cells.sort(key=lambda x: x["count"], reverse=True)
    return cells[:top]


# ----------------------------------------------------------- district_stats ----
def district_stats(cases, socio=None):
    """Per-district rollup: volume, per-capita rate, heinous share, chargesheet rate,
    pendency, risk. When `socio` (district -> {population, ...}) is supplied, each row
    also gets a per-100k crime rate and the risk score folds in a per-capita term.
    Districts without a population row fall back to volume as the per-capita proxy.
    Keep in sync with backend/app/services/aggregations.py."""
    socio = socio or {}
    ref = _ref_now(cases)
    recent_cut = ref - timedelta(days=90)
    by_d = defaultdict(list)
    for c in cases:
        if c.get("district"):
            by_d[c["district"]].append(c)
    max_count = max((len(v) for v in by_d.values()), default=1)
    centroids = district_centroids(cases)

    facts = {}
    for district, rows in by_d.items():
        n = len(rows)
        pop = socio.get(district, {}).get("population")
        facts[district] = {"rows": rows, "n": n,
                           "per_100k": round(n / pop * 100_000, 1) if pop else None}
    max_per_100k = max((f["per_100k"] for f in facts.values() if f["per_100k"]), default=0) or 1

    items = []
    for district, f in facts.items():
        rows, n = f["rows"], f["n"]
        heinous = sum(1 for c in rows if c.get("heinous"))
        finals = [c for c in rows if c.get("cstype")]
        charged = sum(1 for c in finals if c["cstype"] == "A")
        open_n = sum(1 for c in rows if c.get("status_id") == 1)
        recent = sum(1 for c in rows if (_parse(c.get("incident", "")) or ref) > recent_cut)
        heinous_share = heinous / n if n else 0
        cs_rate = charged / len(finals) if finals else 0
        pendency = open_n / n if n else 0
        volume_norm = n / max_count
        per_capita_norm = f["per_100k"] / max_per_100k if f["per_100k"] else volume_norm
        risk = round(0.30 * volume_norm + 0.20 * per_capita_norm + 0.20 * heinous_share
                     + 0.15 * pendency + 0.15 * min(1.0, recent / max(1, n * 0.2)), 3)
        lat, lon = centroids.get(district, (None, None))
        items.append({"district": district, "cases": n, "per_100k": f["per_100k"],
                      "heinous_share": round(heinous_share * 100, 1),
                      "chargesheet_rate": round(cs_rate * 100, 1),
                      "pendency_rate": round(pendency * 100, 1),
                      "recent_90d": recent, "risk_score": risk, "lat": lat, "lon": lon})
    items.sort(key=lambda x: x["cases"], reverse=True)
    return items


def risk_scores(cases, socio=None):
    """risk_scores table: transparent heuristic (primary rank) + ml_tier, an unsupervised
    KMeans signal — see backend/app/services/aggregations.ml_risk_tiers for why this,
    not a fabricated supervised model, is the honest way to add real ML here pending
    Zia AutoML with real labeled outcomes."""
    items = district_stats(cases, socio)
    tiers = ml_risk_tiers(items)
    for it in items:
        it["ml_tier"] = tiers.get(it["district"])
    return items


def ml_risk_tiers(items, k: int = 3):
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


# ------------------------------------------------ trend_baselines + alerts ----
def trend_baselines(cases):
    """Per (district, sub_head) monthly baseline (mean, std)."""
    groups = defaultdict(Counter)  # key -> month -> count
    for c in cases:
        d = _parse(c.get("incident", ""))
        if d:
            groups[(c.get("district", ""), c.get("sub_head", ""))][d.strftime("%Y-%m")] += 1
    out = []
    for (district, sub), months in groups.items():
        counts = list(months.values())
        if len(counts) < 2:
            continue
        mean = sum(counts) / len(counts)
        out.append({"district": district, "sub_head": sub,
                    "baseline_mean": round(mean, 2),
                    "baseline_std": round(statistics.pstdev(counts), 2),
                    "months_observed": len(counts)})
    return out


def spike_alerts(cases, min_recent: int = 8, ratio_threshold: float = 2.0):
    ref = _ref_now(cases)
    window_start = ref - timedelta(days=30)
    centroids = district_centroids(cases)
    groups = defaultdict(list)
    for c in cases:
        d = _parse(c.get("incident", ""))
        if d:
            groups[(c.get("district", ""), c.get("sub_head", ""))].append(d)
    alerts = []
    for (district, sub), dates in groups.items():
        recent = sum(1 for d in dates if d > window_start)
        if recent < min_recent:
            continue
        hist = Counter(d.strftime("%Y-%m") for d in dates if d <= window_start)
        if len(hist) < 2:
            continue
        counts = list(hist.values())
        baseline = sum(counts) / len(counts)
        if baseline <= 0:
            continue
        ratio = recent / baseline
        if ratio < ratio_threshold:
            continue
        std = statistics.pstdev(counts) or 1.0
        lat, lon = centroids.get(district, (None, None))
        alerts.append({"district": district, "sub_head": sub, "recent": recent,
                       "baseline": round(baseline, 1), "ratio": round(ratio, 2),
                       "z": round((recent - baseline) / std, 2),
                       "severity": "Critical" if ratio >= 3 else "Elevated",
                       "lat": lat, "lon": lon, "last_seen": max(dates).strftime("%Y-%m-%d")})
    alerts.sort(key=lambda a: a["ratio"], reverse=True)
    return alerts


# ----------------------------------------------------------- anomalies ----
def anomalies(cases, top_n: int = 12):
    out = []
    by_dm = defaultdict(Counter)
    for c in cases:
        d = _parse(c.get("incident", ""))
        if d:
            by_dm[c.get("district", "")][d.strftime("%Y-%m")] += 1
    for district, months in by_dm.items():
        series = list(months.values())
        if len(series) < 6:
            continue
        mean = sum(series) / len(series)
        std = statistics.pstdev(series) or 1.0
        for month, n in months.items():
            z = (n - mean) / std
            if z >= 2.5 and n >= mean + 5:
                out.append({"kind": "volume", "subject": district, "period": month,
                            "observed": n, "expected": round(mean, 1), "z": round(z, 2),
                            "severity": "High" if z >= 3.2 else "Medium",
                            "description": f"{district} registered {n} cases in {month} — "
                                           f"{z:.1f}σ above its {mean:.0f}/month norm."})
    by_sh = defaultdict(Counter)
    for c in cases:
        if c.get("hour") is not None:
            by_sh[c.get("sub_head", "")][c["hour"]] += 1
    for sub, hours in by_sh.items():
        total = sum(hours.values())
        if total < 50:
            continue
        for hour, n in hours.items():
            p = n / total
            if p < 0.012 and n >= 3:
                out.append({"kind": "temporal", "subject": sub, "period": f"{hour:02d}:00",
                            "observed": n, "expected": round(total / 24, 1),
                            "z": round((p - 1 / 24) / (1 / 24), 2), "severity": "Medium",
                            "description": f"{n} {sub} cases at {hour:02d}:00 — unusual "
                                           f"for this crime ({p*100:.1f}% of its cases)."})
    out.sort(key=lambda a: abs(a["z"]), reverse=True)
    return out[:top_n]


def multivariate_anomalies(cases, contamination: float = 0.08, top_n: int = 8):
    """IsolationForest multivariate anomaly detection — see backend/app/services/
    aggregations.py for the full rationale. Keep in sync with that copy."""
    by_dm = defaultdict(list)
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
        scores = model.score_samples(X)
        cutoff = float(np.percentile(scores, 8))
    except ImportError:  # pragma: no cover — scikit-learn is a hard dependency
        return []
    out = []
    for (district, month, n, heinous_share, cs_rate, pendency), label, score in zip(keys, pred, scores):
        if label != -1:
            continue
        out.append({
            "kind": "multivariate", "subject": district, "period": month, "observed": n,
            "expected": None, "z": round(float(-score), 3),
            "severity": "High" if score <= cutoff else "Medium",
            "description": f"{district} in {month}: an unusual combination of volume "
                           f"({n}), heinous share ({heinous_share*100:.0f}%), chargesheet "
                           f"rate ({cs_rate*100:.0f}%) and pendency ({pendency*100:.0f}%) — "
                           f"flagged by IsolationForest across every district-month.",
            "method": "isolation_forest",
        })
    out.sort(key=lambda a: a["z"], reverse=True)
    return out[:top_n]


# ----------------------------------------------------------- graph_edges ----
def graph_edges(accused_rows, top: int = 5000):
    """Co-accused edges over name-resolved identities (weight = shared FIRs).

    `accused_rows` are raw Accused-table rows; the same physical person across cases
    is resolved by (AccusedName, GenderID) — see ERD_SCHEMA.md conventions.
    networkx centrality is added in the job; this base stays dependency-free."""
    by_case = defaultdict(set)
    for a in accused_rows:
        key = f"{a.get('AccusedName', '')}|{a.get('GenderID', '')}"
        by_case[a.get("CaseMasterID")].add(key)
    weights = Counter()
    for names in by_case.values():
        ordered = sorted(names)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                weights[(ordered[i], ordered[j])] += 1
    return [{"src_person": a, "dst_person": b, "edge_type": "co_accused", "weight": w}
            for (a, b), w in weights.most_common(top)]
