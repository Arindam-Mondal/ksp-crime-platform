"""
Pure aggregation functions for the Catalyst Cron/Event jobs (superset mirror of
`backend/app/services/aggregations.py`). Framework-free; takes list[dict] rows and
returns plain rows ready to UPSERT into the Data Store aggregate tables.

Keep the spike/anomaly/district functions in sync with the backend copy. The extra
functions here (hotspot_cells, graph_edges, risk_scores, trend_baselines) are what the
jobs precompute so the API request path can just SELECT them in catalyst mode.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta

SEVERITY_WEIGHT = {"Low": 1, "Medium": 2, "High": 3, "Severe": 5}
CLEARED = {"Charge-sheeted", "Closed"}


def _parse(dt: str):
    try:
        return datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _ref_now(incidents):
    latest = None
    for r in incidents:
        d = _parse(r.get("datetime", ""))
        if d and (latest is None or d > latest):
            latest = d
    return latest or datetime.now()


def district_centroids(locations):
    acc = defaultdict(list)
    for l in locations:
        try:
            acc[l["district"]].append((float(l["lat"]), float(l["lon"])))
        except (ValueError, KeyError):
            continue
    return {d: (sum(x[0] for x in pts) / len(pts), sum(x[1] for x in pts) / len(pts))
            for d, pts in acc.items() if pts}


# ---------------------------------------------------------- hotspot_cells ----
def hotspot_cells(incidents, precision: int = 2, top: int = 500):
    grid = defaultdict(int)
    for r in incidents:
        try:
            key = (round(float(r["lat"]), precision), round(float(r["lon"]), precision))
        except (ValueError, KeyError):
            continue
        grid[key] += 1
    cells = [{"lat": lat, "lon": lon, "count": c} for (lat, lon), c in grid.items()]
    cells.sort(key=lambda x: x["count"], reverse=True)
    return cells[:top]


# ----------------------------------------------------------- district_stats ----
def district_stats(incidents, locations):
    counts = Counter(r.get("district", "") for r in incidents)
    max_count = max(counts.values()) if counts else 1
    meta, sei_acc = {}, defaultdict(list)
    for l in locations:
        d = l.get("district", "")
        try:
            sei_acc[d].append(float(l["socio_economic_index"]))
        except (ValueError, KeyError):
            pass
        meta.setdefault(d, {"population": l.get("population"), "urban_rural": l.get("urban_rural", "")})
    centroids = district_centroids(locations)
    items = []
    for district, n in counts.items():
        vals = sei_acc.get(district, [0.5])
        avg_sei = sum(vals) / len(vals)
        risk = round(0.7 * (n / max_count) + 0.3 * (1 - avg_sei), 3)
        lat, lon = centroids.get(district, (None, None))
        items.append({"district": district, "incidents": n,
                      "socio_economic_index": round(avg_sei, 3), "risk_score": risk,
                      "population": meta.get(district, {}).get("population"),
                      "urban_rural": meta.get(district, {}).get("urban_rural", ""),
                      "lat": lat, "lon": lon})
    items.sort(key=lambda x: x["incidents"], reverse=True)
    return items


def risk_scores(incidents, locations):
    """risk_scores table (Zia AutoML stand-in: transparent heuristic)."""
    return [{"district": d["district"], "incidents": d["incidents"],
             "socio_economic_index": d["socio_economic_index"], "risk_score": d["risk_score"]}
            for d in district_stats(incidents, locations)]


# ------------------------------------------------ trend_baselines + alerts ----
def trend_baselines(incidents):
    """Per (district, crime_type) monthly baseline (mean, std)."""
    groups = defaultdict(Counter)  # key -> month -> count
    for r in incidents:
        d = _parse(r.get("datetime", ""))
        if d:
            groups[(r.get("district", ""), r.get("crime_type", ""))][d.strftime("%Y-%m")] += 1
    out = []
    for (district, crime), months in groups.items():
        counts = list(months.values())
        if len(counts) < 2:
            continue
        mean = sum(counts) / len(counts)
        out.append({"district": district, "crime_type": crime,
                    "baseline_mean": round(mean, 2),
                    "baseline_std": round(statistics.pstdev(counts), 2),
                    "months_observed": len(counts)})
    return out


def spike_alerts(incidents, locations, min_recent: int = 8, ratio_threshold: float = 2.0):
    ref = _ref_now(incidents)
    window_start = ref - timedelta(days=30)
    centroids = district_centroids(locations)
    groups = defaultdict(list)
    for r in incidents:
        d = _parse(r.get("datetime", ""))
        if d:
            groups[(r.get("district", ""), r.get("crime_type", ""))].append(d)
    alerts = []
    for (district, crime), dates in groups.items():
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
        alerts.append({"district": district, "crime_type": crime, "recent": recent,
                       "baseline": round(baseline, 1), "ratio": round(ratio, 2),
                       "z": round((recent - baseline) / std, 2),
                       "severity": "Critical" if ratio >= 3 else "Elevated",
                       "lat": lat, "lon": lon, "last_seen": max(dates).strftime("%Y-%m-%d")})
    alerts.sort(key=lambda a: a["ratio"], reverse=True)
    return alerts


# ----------------------------------------------------------- anomalies ----
def anomalies(incidents, top_n: int = 12):
    out = []
    by_dm = defaultdict(Counter)
    for r in incidents:
        d = _parse(r.get("datetime", ""))
        if d:
            by_dm[r.get("district", "")][d.strftime("%Y-%m")] += 1
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
                            "description": f"{district} logged {n} incidents in {month} — "
                                           f"{z:.1f}σ above its {mean:.0f}/month norm."})
    by_ch = defaultdict(Counter)
    for r in incidents:
        d = _parse(r.get("datetime", ""))
        if d:
            by_ch[r.get("crime_type", "")][d.hour] += 1
    for crime, hours in by_ch.items():
        total = sum(hours.values())
        if total < 50:
            continue
        for hour, n in hours.items():
            p = n / total
            if p < 0.012 and n >= 3:
                out.append({"kind": "temporal", "subject": crime, "period": f"{hour:02d}:00",
                            "observed": n, "expected": round(total / 24, 1),
                            "z": round((p - 1 / 24) / (1 / 24), 2), "severity": "Medium",
                            "description": f"{n} {crime} incidents at {hour:02d}:00 — unusual "
                                           f"for this crime ({p*100:.1f}% of its cases)."})
    out.sort(key=lambda a: abs(a["z"]), reverse=True)
    return out[:top_n]


# ----------------------------------------------------------- graph_edges ----
def graph_edges(incident_persons, top: int = 5000):
    """Co-offender edges (weight = shared incidents). networkx centrality is added in
    the job; this base function stays dependency-free for portability."""
    by_incident = defaultdict(list)
    for l in incident_persons:
        if l.get("role") == "offender":
            by_incident[l["incident_id"]].append(l["person_id"])
    weights = Counter()
    for offenders in by_incident.values():
        for i in range(len(offenders)):
            for j in range(i + 1, len(offenders)):
                a, b = sorted((offenders[i], offenders[j]))
                weights[(a, b)] += 1
    edges = [{"src_person": a, "dst_person": b, "edge_type": "co_offender", "weight": w}
             for (a, b), w in weights.most_common(top)]
    return edges
