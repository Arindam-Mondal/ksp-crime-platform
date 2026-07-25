"""
Cross-cutting analytics over the FIR ERD: KPIs, crime classification mixes, the
investigation funnel (FIR → final report → court → disposal), act/section usage,
arrest analytics, officer/court workload, and party demographics.

Local mode derives everything from the case view on the fly. In production these
become precomputed rollup tables written by Cron jobs and simply SELECTed here
(see CLAUDE.md precompute-and-serve). Keep everything cheap and read-only.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict

from fastapi import APIRouter

from app.services import aggregations, firdata, reference
from app.services.datastore import get_store

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

AGE_ORDER = ["<18", "18-25", "26-35", "36-45", "46-60", "60+"]
GENDER_LABEL = {"M": "Male", "F": "Female", "T": "Transgender"}


def _age_group(age: int | None) -> str | None:
    if age is None:
        return None
    if age < 18:
        return "<18"
    if age <= 25:
        return "18-25"
    if age <= 35:
        return "26-35"
    if age <= 45:
        return "36-45"
    if age <= 60:
        return "46-60"
    return "60+"


def _ordered(counter: Counter, order: list[str]) -> list[dict]:
    out = [{"group": g, "count": counter.get(g, 0)} for g in order]
    extras = [{"group": k, "count": v} for k, v in counter.items() if k not in order and k]
    extras.sort(key=lambda x: x["count"], reverse=True)
    return out + extras


@router.get("/summary")
def summary():
    """Top-line KPIs for the command overview."""
    rows = firdata.cases()
    total = len(rows)
    if not total:
        return {"total_cases": 0}

    districts = Counter(r["district"] for r in rows if r["district"])
    subs = Counter(r["sub_head"] for r in rows if r["sub_head"])
    finals = [r for r in rows if r["cstype"]]
    charged = [r for r in finals if r["cstype"] == "A"]
    convicted = sum(1 for r in rows if r["status"] == "Convicted")
    acquitted = sum(1 for r in rows if r["status"] == "Acquitted")
    heinous = sum(1 for r in rows if r["heinous"])
    cyber = sum(1 for r in rows if r["head"] == "Cyber Crime")
    open_n = sum(1 for r in rows if r["status_id"] == 1)
    delays = [r["report_delay_days"] for r in rows if r["report_delay_days"] is not None]
    cs_days = [r["cs_days"] for r in charged if r["cs_days"] is not None]
    arrests_total = sum(r["n_arrests"] for r in rows)
    repeat = sum(1 for o in firdata.offenders()["by_id"].values() if o["n_cases"] >= 2)

    return {
        "total_cases": total,
        "fir_cases": sum(1 for r in rows if r["category"] == "FIR"),
        "districts": len(districts),
        "police_stations": len({r["station_id"] for r in rows}),
        "chargesheet_rate": round(len(charged) / len(finals) * 100, 1) if finals else 0,
        "pendency_rate": round(open_n / total * 100, 1),
        "conviction_rate": round(convicted / (convicted + acquitted) * 100, 1)
                           if (convicted + acquitted) else 0,
        "heinous_share": round(heinous / total * 100, 1),
        "cyber_share": round(cyber / total * 100, 1),
        "avg_report_delay_days": round(sum(delays) / len(delays), 1) if delays else 0,
        "median_days_to_chargesheet": round(statistics.median(cs_days), 0) if cs_days else 0,
        "arrests_total": arrests_total,
        "repeat_offenders": repeat,
        "top_district": districts.most_common(1)[0][0],
        "top_district_count": districts.most_common(1)[0][1],
        "top_sub_head": subs.most_common(1)[0][0],
        "top_sub_head_count": subs.most_common(1)[0][1],
    }


@router.get("/by-crime-head")
def by_crime_head():
    rows = firdata.cases()
    counts = Counter(r["head"] for r in rows if r["head"])
    return {"items": [{"crime_head": h, "count": n} for h, n in counts.most_common()]}


@router.get("/by-sub-head")
def by_sub_head():
    """Case counts per crime sub-head with parent head + heinous share + chargesheet rate."""
    rows = firdata.cases()
    by_sub: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["sub_head"]:
            by_sub[r["sub_head"]].append(r)
    items = []
    for sub, rs in sorted(by_sub.items(), key=lambda kv: -len(kv[1])):
        finals = [r for r in rs if r["cstype"]]
        charged = sum(1 for r in finals if r["cstype"] == "A")
        items.append({
            "sub_head": sub,
            "crime_head": rs[0]["head"],
            "count": len(rs),
            "heinous_share": round(sum(1 for r in rs if r["heinous"]) / len(rs) * 100, 1),
            "chargesheet_rate": round(charged / len(finals) * 100, 1) if finals else 0,
        })
    return {"items": items}


@router.get("/by-category")
def by_category():
    """FIR / Zero FIR / UDR / PAR mix (CrimeNo first-digit taxonomy)."""
    rows = firdata.cases()
    counts = Counter(r["category"] for r in rows if r["category"])
    return {"items": [{"category": c, "count": n} for c, n in counts.most_common()]}


@router.get("/by-gravity")
def by_gravity():
    rows = firdata.cases()
    counts = Counter(r["gravity"] for r in rows if r["gravity"])
    return {"items": [{"gravity": g, "count": n} for g, n in counts.most_common()]}


@router.get("/by-status")
def by_status():
    rows = firdata.cases()
    counts = Counter(r["status"] for r in rows if r["status"])
    total = sum(counts.values()) or 1
    finals = [r for r in rows if r["cstype"]]
    charged = sum(1 for r in finals if r["cstype"] == "A")
    items = [{"status": s, "count": n, "in_court": s in
              {"Charge Sheeted", "Pending Trial", "Convicted", "Acquitted"}}
             for s, n in counts.most_common()]
    return {"items": items,
            "chargesheet_rate": round(charged / len(finals) * 100, 1) if finals else 0,
            "pendency_rate": round(sum(1 for r in rows if r["status_id"] == 1) / total * 100, 1)}


@router.get("/case-funnel")
def case_funnel():
    """Investigation pipeline: registered → final report → chargesheet → trial → disposal,
    with the B/C/other leakage called out."""
    rows = firdata.cases()
    total = len(rows)
    finals = [r for r in rows if r["cstype"]]
    a = sum(1 for r in finals if r["cstype"] == "A")
    b = sum(1 for r in finals if r["cstype"] == "B")
    c = sum(1 for r in finals if r["cstype"] == "C")
    in_trial = sum(1 for r in rows if r["status"] in {"Charge Sheeted", "Pending Trial"})
    convicted = sum(1 for r in rows if r["status"] == "Convicted")
    acquitted = sum(1 for r in rows if r["status"] == "Acquitted")
    stages = [
        {"stage": "Cases registered", "count": total},
        {"stage": "Final report filed", "count": len(finals)},
        {"stage": "Chargesheeted (A)", "count": a},
        {"stage": "In trial", "count": in_trial + convicted + acquitted},
        {"stage": "Disposed by court", "count": convicted + acquitted},
        {"stage": "Convicted", "count": convicted},
    ]
    leakage = [
        {"label": "Under investigation", "count": sum(1 for r in rows if r["status_id"] == 1)},
        {"label": "False case (B report)", "count": b},
        {"label": "Undetected (C report)", "count": c},
        {"label": "Acquitted", "count": acquitted},
        {"label": "Transferred / others", "count": sum(1 for r in rows
                                                       if r["status"] in {"Transferred", "Closed - Others"})},
    ]
    return {"stages": stages, "leakage": leakage}


@router.get("/by-month")
def by_month():
    """Monthly trend of incidents, split by crime head for a stacked time series."""
    rows = firdata.cases()
    heads = sorted({r["head"] for r in rows if r["head"]})
    buckets: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        if len(r["month"]) == 7:
            buckets[r["month"]][r["head"] or "Other"] += 1
    items = []
    for month in sorted(buckets):
        row = {"month": month, "total": sum(buckets[month].values())}
        for h in heads:
            row[h] = buckets[month].get(h, 0)
        items.append(row)
    return {"heads": heads, "items": items}


@router.get("/top-sections")
def top_sections(limit: int = 15):
    """Most-invoked act/sections across all FIRs (from ActSectionAssociation)."""
    lk = firdata.lookups()
    counts: Counter = Counter()
    for r in get_store().rows("ActSectionAssociation"):
        counts[(r["ActID"], r["SectionID"])] += 1
    items = []
    for (act, sec), n in counts.most_common(limit):
        items.append({
            "act": lk["acts"].get(act, act),
            "section": sec,
            "label": f"{lk['acts'].get(act, act)} {sec}",
            "description": lk["sections"].get((act, sec), ""),
            "count": n,
        })
    return {"items": items}


@router.get("/arrests")
def arrest_analytics():
    """Arrest/surrender analytics from the ArrestSurrender table."""
    arr = firdata.arrests()["rows"]
    cidx = firdata.case_index()
    total = len(arr)
    surrender = sum(1 for a in arr if a["type"] == "Surrender")
    out_of_state = sum(1 for a in arr if a["state"] and a["state"] != "Karnataka")

    by_month: Counter = Counter()
    for a in arr:
        if len(a["date"]) >= 7:
            by_month[a["date"][:7]] += 1

    lag_by_head: dict[str, list[int]] = defaultdict(list)
    for c in cidx.values():
        if c["first_arrest_days"] is not None and c["head"]:
            lag_by_head[c["head"]].append(c["first_arrest_days"])
    lags = [{"crime_head": h, "median_days_to_arrest": round(statistics.median(v), 0),
             "arrained_cases": len(v)}
            for h, v in sorted(lag_by_head.items(), key=lambda kv: -len(kv[1]))]

    top_districts = Counter(a["district"] for a in arr if a["district"]).most_common(10)
    return {
        "total": total,
        "arrests": total - surrender,
        "surrenders": surrender,
        "out_of_state": out_of_state,
        "by_month": [{"month": m, "count": by_month[m]} for m in sorted(by_month)],
        "days_to_arrest_by_head": lags,
        "top_districts": [{"district": d, "count": n} for d, n in top_districts],
    }


@router.get("/officers")
def officer_workload():
    """Investigating-officer workload: chargesheets + arrests handled, by officer & rank."""
    lk = firdata.lookups()
    cs_by_officer: Counter = Counter()
    a_by_officer: Counter = Counter()
    for r in get_store().rows("ChargesheetDetails"):
        oid = int(r["PolicePersonID"]) if str(r["PolicePersonID"]).strip() else None
        if oid:
            cs_by_officer[oid] += 1
            if str(r["cstype"]).strip().upper() == "A":
                a_by_officer[oid] += 1
    arrest_by_officer: Counter = Counter()
    for a in firdata.arrests()["rows"]:
        if a["io_id"]:
            arrest_by_officer[a["io_id"]] += 1

    active = set(cs_by_officer) | set(arrest_by_officer)
    items = []
    for oid in active:
        emp = lk["employees"].get(oid, {})
        unit = lk["units"].get(emp.get("unit_id"), {})
        district = lk["districts"].get(emp.get("district_id"), "")
        cs_n = cs_by_officer.get(oid, 0)
        items.append({
            "employee_id": oid,
            "name": emp.get("name", f"Emp {oid}"),
            "rank": emp.get("rank", ""),
            "station": unit.get("name", ""),
            "district": district,
            "chargesheets": cs_n,
            "arrests": arrest_by_officer.get(oid, 0),
            "chargesheet_success": round(a_by_officer.get(oid, 0) / cs_n * 100, 1) if cs_n else 0,
        })
    items.sort(key=lambda x: -(x["chargesheets"] + x["arrests"]))

    rank_counts = Counter(lk["employees"][e]["rank"] for e in lk["employees"])
    return {
        "total_employees": len(lk["employees"]),
        "active_investigators": len(active),
        "by_rank": [{"rank": r, "count": n} for r, n in rank_counts.most_common()],
        "top": items[:15],
    }


@router.get("/courts")
def court_load():
    """Per-court caseload from CaseMaster.CourtID + trial-stage statuses."""
    rows = firdata.cases()
    by_court: dict[str, dict] = {}
    for r in rows:
        if not r["court"]:
            continue
        d = by_court.setdefault(r["court"], {
            "court": r["court"], "district": r["district"], "cases": 0,
            "pending_trial": 0, "convicted": 0, "acquitted": 0,
        })
        d["cases"] += 1
        if r["status"] in {"Charge Sheeted", "Pending Trial"}:
            d["pending_trial"] += 1
        elif r["status"] == "Convicted":
            d["convicted"] += 1
        elif r["status"] == "Acquitted":
            d["acquitted"] += 1
    items = sorted(by_court.values(), key=lambda x: -x["cases"])
    return {"total_courts": len(items), "items": items[:20]}


@router.get("/demographics")
def demographics():
    """Party demographics straight from the ERD's party tables: victim & accused
    age/gender profiles, complainant occupation / religion / caste mix."""
    pts = firdata.parties()

    vic_age, vic_gender = Counter(), Counter()
    police_victims = 0
    for rows in pts["victims"].values():
        for v in rows:
            g = _age_group(v["age"])
            if g:
                vic_age[g] += 1
            vic_gender[GENDER_LABEL.get(v["gender"], v["gender"])] += 1
            if v["police"]:
                police_victims += 1

    acc_age, acc_gender = Counter(), Counter()
    for rows in pts["accused"].values():
        for a in rows:
            g = _age_group(a["age"])
            if g:
                acc_age[g] += 1
            acc_gender[GENDER_LABEL.get(a["gender"], a["gender"])] += 1

    comp_occ, comp_rel, comp_caste, comp_gender = Counter(), Counter(), Counter(), Counter()
    for rows in pts["complainants"].values():
        for c in rows:
            if c["occupation"]:
                comp_occ[c["occupation"]] += 1
            if c["religion"]:
                comp_rel[c["religion"]] += 1
            if c["caste"]:
                comp_caste[c["caste"]] += 1
            comp_gender[GENDER_LABEL.get(c["gender"], c["gender"])] += 1

    def top(counter: Counter, n: int = 12) -> list[dict]:
        return [{"group": k, "count": v} for k, v in counter.most_common(n)]

    return {
        "victim_age_groups": _ordered(vic_age, AGE_ORDER),
        "accused_age_groups": _ordered(acc_age, AGE_ORDER),
        "victim_gender": top(vic_gender),
        "accused_gender": top(acc_gender),
        "police_victims": police_victims,
        "complainant_occupation": top(comp_occ),
        "complainant_religion": top(comp_rel),
        "complainant_caste": top(comp_caste),
        "complainant_gender": top(comp_gender),
    }


@router.get("/investigation")
def investigation_timing():
    """Reporting delay + time-to-chargesheet by crime head (process efficiency view)."""
    rows = firdata.cases()
    delay_by_sub: dict[str, list[float]] = defaultdict(list)
    cs_by_head: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        if r["report_delay_days"] is not None and r["sub_head"]:
            delay_by_sub[r["sub_head"]].append(r["report_delay_days"])
        if r["cs_days"] is not None and r["cstype"] == "A" and r["head"]:
            cs_by_head[r["head"]].append(r["cs_days"])
    report_delay = [{"sub_head": s, "avg_days": round(sum(v) / len(v), 1), "cases": len(v)}
                    for s, v in delay_by_sub.items() if len(v) >= 30]
    report_delay.sort(key=lambda x: -x["avg_days"])
    cs_time = [{"crime_head": h, "median_days": round(statistics.median(v), 0), "cases": len(v)}
               for h, v in cs_by_head.items()]
    cs_time.sort(key=lambda x: -x["median_days"])
    return {"report_delay": report_delay[:12], "days_to_chargesheet": cs_time}


@router.get("/socioeconomic")
def socioeconomic():
    """The 'why behind the where': per-district crime rate per 100k population,
    correlated against urbanisation, literacy and population density (Census 2011).

    Volume-ranked hotspots can mislead — a populous district looks dangerous simply for
    being big. This normalises crime by population and surfaces which socio-economic
    factors actually track higher crime rates."""
    data = aggregations.socioeconomic_correlation(firdata.cases(), reference.socioeconomic())
    # Contrast: how districts reorder when ranked by rate vs raw volume (the key insight).
    by_volume = sorted(data["items"], key=lambda x: -x["cases"])
    vol_rank = {d["district"]: i + 1 for i, d in enumerate(by_volume)}
    for i, it in enumerate(data["items"]):  # data["items"] is already rate-sorted
        it["rate_rank"] = i + 1
        it["volume_rank"] = vol_rank[it["district"]]
        it["rank_shift"] = it["volume_rank"] - it["rate_rank"]
    return data
