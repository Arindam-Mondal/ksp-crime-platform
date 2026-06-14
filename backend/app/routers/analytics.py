"""
Cross-cutting analytics aggregates for the dashboard & demographics views.

Phase 0 scaffold: derived on the fly from the CSV so the UI is rich and insightful.
In production these become precomputed `district_stats` / demographic rollup tables
written by Cron jobs and simply SELECTed here (see CLAUDE.md precompute-and-serve).
Keep everything here cheap and read-only.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter

from app.services.datastore import get_store

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

AGE_ORDER = ["<18", "18-25", "26-35", "36-45", "46-60", "60+"]
CLEARED = {"Charge-sheeted", "Closed"}
SEV_ORDER = ["Low", "Medium", "High", "Severe"]


def _ordered(counter: Counter, order: list[str]) -> list[dict]:
    """Counter -> [{group,count}] in a fixed order (zero-filled), then any extras by count."""
    out = [{"group": g, "count": counter.get(g, 0)} for g in order]
    extras = [{"group": k, "count": v} for k, v in counter.items() if k not in order]
    extras.sort(key=lambda x: x["count"], reverse=True)
    return out + extras


@router.get("/summary")
def summary():
    """Top-line KPIs for the command overview."""
    inc = get_store().rows("incidents")
    total = len(inc)
    if not total:
        return {"total_incidents": 0, "districts": 0, "crime_types": 0,
                "clearance_rate": 0, "cyber_share": 0, "severe_share": 0,
                "weapon_share": 0, "avg_fir_delay": 0, "top_district": None, "top_crime": None}

    districts = Counter(r["district"] for r in inc)
    crimes = Counter(r["crime_type"] for r in inc)
    cleared = sum(1 for r in inc if r.get("status") in CLEARED)
    cyber = sum(1 for r in inc if r.get("crime_type") == "Cybercrime")
    severe = sum(1 for r in inc if r.get("severity") == "Severe")
    weapon = sum(1 for r in inc if r.get("weapon") == "Yes")
    delays = [float(r["fir_delay_days"]) for r in inc if r.get("fir_delay_days", "").strip() != ""]

    return {
        "total_incidents": total,
        "districts": len(districts),
        "crime_types": len(crimes),
        "clearance_rate": round(cleared / total * 100, 1),
        "cyber_share": round(cyber / total * 100, 1),
        "severe_share": round(severe / total * 100, 1),
        "weapon_share": round(weapon / total * 100, 1),
        "avg_fir_delay": round(sum(delays) / len(delays), 1) if delays else 0,
        "top_district": districts.most_common(1)[0][0],
        "top_district_count": districts.most_common(1)[0][1],
        "top_crime": crimes.most_common(1)[0][0],
        "top_crime_count": crimes.most_common(1)[0][1],
    }


@router.get("/by-crime-type")
def by_crime_type():
    """Incident counts per crime type, tagged with head + severity."""
    inc = get_store().rows("incidents")
    counts = Counter(r["crime_type"] for r in inc)
    head = {r["crime_type"]: r.get("crime_head", "Other") for r in inc}
    sev = {r["crime_type"]: r.get("severity", "Medium") for r in inc}
    items = [{"crime_type": c, "crime_head": head.get(c, "Other"),
              "severity": sev.get(c, "Medium"), "count": n}
             for c, n in counts.most_common()]
    return {"items": items}


@router.get("/by-crime-head")
def by_crime_head():
    inc = get_store().rows("incidents")
    counts = Counter(r.get("crime_head", "Other") for r in inc)
    return {"items": [{"crime_head": h, "count": n} for h, n in counts.most_common()]}


@router.get("/by-status")
def by_status():
    inc = get_store().rows("incidents")
    counts = Counter(r.get("status", "Unknown") for r in inc)
    total = sum(counts.values()) or 1
    cleared = sum(n for s, n in counts.items() if s in CLEARED)
    items = [{"status": s, "count": n, "cleared": s in CLEARED} for s, n in counts.most_common()]
    return {"items": items, "clearance_rate": round(cleared / total * 100, 1)}


@router.get("/by-severity")
def by_severity():
    inc = get_store().rows("incidents")
    counts = Counter(r.get("severity", "Medium") for r in inc)
    return {"items": [{"severity": s, "count": counts.get(s, 0)} for s in SEV_ORDER]}


@router.get("/by-month")
def by_month():
    """Monthly trend, split by crime head for a stacked time series."""
    inc = get_store().rows("incidents")
    heads = sorted({r.get("crime_head", "Other") for r in inc})
    buckets: dict[str, Counter] = defaultdict(Counter)
    for r in inc:
        month = r.get("datetime", "")[:7]  # YYYY-MM
        if len(month) == 7:
            buckets[month][r.get("crime_head", "Other")] += 1
    items = []
    for month in sorted(buckets):
        row = {"month": month, "total": sum(buckets[month].values())}
        for h in heads:
            row[h] = buckets[month].get(h, 0)
        items.append(row)
    return {"heads": heads, "items": items}


@router.get("/demographics")
def demographics():
    """Victim & offender age-group / gender distributions, plus urban-rural split."""
    inc = get_store().rows("incidents")

    victim_age = Counter(r.get("victim_age_group", "") for r in inc if r.get("victim_age_group"))
    victim_gender = Counter(r.get("victim_gender", "") for r in inc if r.get("victim_gender"))
    urban_rural = Counter(r.get("urban_rural", "") for r in inc if r.get("urban_rural"))

    # Offender demographics, incident-weighted (join links -> persons).
    persons = {p["id"]: p for p in get_store().rows("persons")}
    links = get_store().rows("incident_persons")
    off_age, off_gender = Counter(), Counter()
    for l in links:
        if l.get("role") != "offender":
            continue
        p = persons.get(l.get("person_id"))
        if not p:
            continue
        if p.get("age_group"):
            off_age[p["age_group"]] += 1
        if p.get("gender"):
            off_gender[p["gender"]] += 1

    def gender_items(c: Counter) -> list[dict]:
        labels = {"M": "Male", "F": "Female"}
        return [{"gender": labels.get(g, g), "count": n} for g, n in c.most_common()]

    return {
        "victim_age_groups": _ordered(victim_age, AGE_ORDER),
        "offender_age_groups": _ordered(off_age, AGE_ORDER),
        "victim_gender": gender_items(victim_gender),
        "offender_gender": gender_items(off_gender),
        "urban_rural": [{"group": g, "count": n} for g, n in urban_rural.most_common()],
    }
