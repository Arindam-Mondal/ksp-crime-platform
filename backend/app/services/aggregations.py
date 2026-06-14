"""
Pure aggregation functions — the heavy math, framework-free.

The API request path calls these in local mode (DATA_MODE=local). The Catalyst
Cron/Event jobs use a mirrored copy in `functions/common/aggregations.py` to write
the same results into aggregate tables; in catalyst mode the API just SELECTs those.
Keep the two copies in sync.

Everything here takes already-loaded list[dict] rows (CSV/ZCQL agnostic) and returns
plain dicts/lists so it serialises straight to JSON.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta

SEVERITY_WEIGHT = {"Low": 1, "Medium": 2, "High": 3, "Severe": 5}


# ---------------------------------------------------------------- helpers ----
def _parse(dt: str) -> datetime | None:
    try:
        return datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _ref_now(incidents: list[dict]) -> datetime:
    """Reference 'now' = latest incident timestamp (synthetic data ends ~today)."""
    latest = None
    for r in incidents:
        d = _parse(r.get("datetime", ""))
        if d and (latest is None or d > latest):
            latest = d
    return latest or datetime.now()


def district_centroids(locations: list[dict]) -> dict[str, tuple[float, float]]:
    acc: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for l in locations:
        try:
            acc[l["district"]].append((float(l["lat"]), float(l["lon"])))
        except (ValueError, KeyError):
            continue
    return {d: (sum(x[0] for x in pts) / len(pts), sum(x[1] for x in pts) / len(pts))
            for d, pts in acc.items() if pts}


# --------------------------------------------------- A: spike / trend alerts ----
def spike_alerts(incidents: list[dict], locations: list[dict],
                 min_recent: int = 8, ratio_threshold: float = 2.0) -> list[dict]:
    """Per (district, crime_type): last-30-day volume vs historical monthly baseline."""
    ref = _ref_now(incidents)
    window_start = ref - timedelta(days=30)
    centroids = district_centroids(locations)

    # group dated incidents by (district, crime_type)
    groups: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    for r in incidents:
        d = _parse(r.get("datetime", ""))
        if d:
            groups[(r.get("district", ""), r.get("crime_type", ""))].append(d)

    alerts = []
    for (district, crime), dates in groups.items():
        recent = sum(1 for d in dates if d > window_start)
        if recent < min_recent:
            continue
        # historical monthly counts (months strictly before the recent window)
        hist_months: Counter = Counter()
        for d in dates:
            if d <= window_start:
                hist_months[d.strftime("%Y-%m")] += 1
        if len(hist_months) < 2:
            continue
        counts = list(hist_months.values())
        baseline = sum(counts) / len(counts)               # avg incidents / month
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
            "crime_type": crime,
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
def anomalies(incidents: list[dict], top_n: int = 12) -> list[dict]:
    """Transparent statistical outliers: district monthly-volume spikes + rare-hour crimes."""
    out: list[dict] = []

    # (1) district monthly-volume z-scores
    by_district_month: dict[str, Counter] = defaultdict(Counter)
    for r in incidents:
        d = _parse(r.get("datetime", ""))
        if d:
            by_district_month[r.get("district", "")][d.strftime("%Y-%m")] += 1
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
                    "description": f"{district} logged {n} incidents in {month} — "
                                   f"{z:.1f}σ above its {mean:.0f}/month norm.",
                })

    # (2) crimes at a rare hour for their type
    by_crime_hour: dict[str, Counter] = defaultdict(Counter)
    for r in incidents:
        d = _parse(r.get("datetime", ""))
        if d:
            by_crime_hour[r.get("crime_type", "")][d.hour] += 1
    for crime, hours in by_crime_hour.items():
        total = sum(hours.values())
        if total < 50:
            continue
        for hour, n in hours.items():
            p = n / total
            if p < 0.012 and n >= 3:
                out.append({
                    "kind": "temporal",
                    "subject": crime,
                    "period": f"{hour:02d}:00",
                    "observed": n,
                    "expected": round(total / 24, 1),
                    "z": round((p - 1 / 24) / (1 / 24), 2),
                    "severity": "Medium",
                    "description": f"{n} {crime} incidents at {hour:02d}:00 — an unusual hour "
                                   f"for this crime ({p*100:.1f}% of its cases).",
                })

    out.sort(key=lambda a: abs(a["z"]), reverse=True)
    return out[:top_n]


# ------------------------------------------ D: district stats + drill-down ----
def district_stats(incidents: list[dict], locations: list[dict]) -> list[dict]:
    """Per-district rollup: volume, SEI, heuristic risk, centroid, urbanisation."""
    counts = Counter(r.get("district", "") for r in incidents)
    max_count = max(counts.values()) if counts else 1

    meta: dict[str, dict] = {}
    sei_acc: dict[str, list[float]] = defaultdict(list)
    for l in locations:
        d = l.get("district", "")
        try:
            sei_acc[d].append(float(l["socio_economic_index"]))
        except (ValueError, KeyError):
            pass
        if d not in meta:
            meta[d] = {
                "population": int(l["population"]) if str(l.get("population", "")).isdigit() else None,
                "urban_rural": l.get("urban_rural", ""),
                "archetype": l.get("archetype", ""),
            }
    centroids = district_centroids(locations)

    items = []
    for district, n in counts.items():
        sei_vals = sei_acc.get(district, [0.5])
        avg_sei = sum(sei_vals) / len(sei_vals)
        risk = round(0.7 * (n / max_count) + 0.3 * (1 - avg_sei), 3)
        lat, lon = centroids.get(district, (None, None))
        m = meta.get(district, {})
        items.append({
            "district": district,
            "incidents": n,
            "socio_economic_index": round(avg_sei, 3),
            "risk_score": risk,
            "population": m.get("population"),
            "urban_rural": m.get("urban_rural", ""),
            "lat": lat,
            "lon": lon,
        })
    items.sort(key=lambda x: x["incidents"], reverse=True)
    return items


def station_breakdown(incidents: list[dict], locations: list[dict], district: str) -> dict:
    """Drill-down for one district: station counts, top crime types, hourly profile."""
    rows = [r for r in incidents if r.get("district") == district]
    station_coords = {l["station"]: (float(l["lat"]), float(l["lon"]))
                      for l in locations if l.get("district") == district
                      and l.get("lat") and l.get("lon")}
    station_counts = Counter(r.get("station", "") for r in rows)
    stations = [
        {"station": s, "incidents": n,
         "lat": station_coords.get(s, (None, None))[0],
         "lon": station_coords.get(s, (None, None))[1]}
        for s, n in station_counts.most_common()
    ]
    by_type = [{"name": c, "count": n}
               for c, n in Counter(r.get("crime_type", "") for r in rows).most_common()]
    hours = Counter()
    for r in rows:
        d = _parse(r.get("datetime", ""))
        if d:
            hours[d.hour] += 1
    by_hour = [{"hour": h, "count": hours.get(h, 0)} for h in range(24)]
    return {
        "district": district,
        "total": len(rows),
        "stations": stations,
        "by_type": by_type,
        "by_hour": by_hour,
    }
