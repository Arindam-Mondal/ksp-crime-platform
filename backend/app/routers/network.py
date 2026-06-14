"""
Pillar 2 — network / link analysis + person intelligence.

Production: serve the precomputed `graph_edges` table (networkx centrality computed
by a Cron/Event job). Phase 0 scaffold: build co-offender graphs and per-person
briefings on the fly from `incident_persons` + `incidents`. A single person's slice
is tiny, so these joins stay well under the 300-row Catalyst cap.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter, HTTPException

from app.services.datastore import get_store

router = APIRouter(prefix="/api/network", tags=["network"])

SEVERITY_WEIGHT = {"Low": 1, "Medium": 2, "High": 3, "Severe": 5}
CLEARED = {"Charge-sheeted", "Closed"}


def _offenders_by_incident() -> dict[str, list[str]]:
    links = get_store().rows("incident_persons")
    by_incident: dict[str, list[str]] = defaultdict(list)
    for l in links:
        if l.get("role") == "offender":
            by_incident[l["incident_id"]].append(l["person_id"])
    return by_incident


def _offender_incident_counts() -> Counter:
    links = get_store().rows("incident_persons")
    return Counter(l["person_id"] for l in links if l.get("role") == "offender")


def _adjacency(by_incident: dict[str, list[str]]) -> dict[str, Counter]:
    """person -> Counter of co-offenders weighted by shared incidents."""
    adj: dict[str, Counter] = defaultdict(Counter)
    for offenders in by_incident.values():
        for i in range(len(offenders)):
            for j in range(i + 1, len(offenders)):
                a, b = offenders[i], offenders[j]
                adj[a][b] += 1
                adj[b][a] += 1
    return adj


@router.get("/top-offenders")
def top_offenders(limit: int = 20):
    """Repeat offenders ranked by incident count."""
    counts = _offender_incident_counts()
    persons = {p["id"]: p for p in get_store().rows("persons")}
    items = [
        {
            "person_id": pid,
            "name": persons.get(pid, {}).get("name", pid),
            "gender": persons.get(pid, {}).get("gender", "M"),
            "incidents": n,
        }
        for pid, n in counts.most_common(limit)
    ]
    return {"items": items}


@router.get("/ego/{person_id}")
def ego_graph(person_id: str, depth: int = 1):
    """Co-offender graph around a person (nodes + edges for the force graph).

    Nodes carry identity metadata (name, gender, incident count) so the client can
    render avatars / size nodes without a call per node.
    """
    by_incident = _offenders_by_incident()
    persons = {p["id"]: p for p in get_store().rows("persons")}
    if person_id not in persons:
        raise HTTPException(status_code=404, detail="person not found")

    counts = _offender_incident_counts()
    adj = _adjacency(by_incident)

    frontier = {person_id}
    seen = {person_id}
    edges = []
    for _ in range(max(1, depth)):
        nxt = set()
        for node in frontier:
            for neighbor, weight in adj[node].items():
                edges.append({"source": node, "target": neighbor, "weight": weight})
                if neighbor not in seen:
                    seen.add(neighbor)
                    nxt.add(neighbor)
        frontier = nxt

    nodes = [
        {
            "id": pid,
            "name": persons.get(pid, {}).get("name", pid),
            "gender": persons.get(pid, {}).get("gender", "M"),
            "incidents": counts.get(pid, 0),
            "is_root": pid == person_id,
        }
        for pid in seen
    ]
    # de-dup undirected edges
    uniq = {tuple(sorted((e["source"], e["target"]))): e for e in edges}
    return {"root": person_id, "nodes": nodes, "edges": list(uniq.values())}


def _person_incident_ids(person_id: str, role: str = "offender") -> list[str]:
    links = get_store().rows("incident_persons")
    return [l["incident_id"] for l in links if l.get("person_id") == person_id and l.get("role") == role]


@router.get("/person/{person_id}")
def person_profile(person_id: str):
    """Self-contained briefing for one person: identity, stats, threat, crimes,
    timeline, crime mix, MO tags, and ranked associates."""
    persons = {p["id"]: p for p in get_store().rows("persons")}
    person = persons.get(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="person not found")

    incidents = {r["id"]: r for r in get_store().rows("incidents")}
    offender_ids = _person_incident_ids(person_id, "offender")
    victim_ids = _person_incident_ids(person_id, "victim")
    crimes = [incidents[i] for i in offender_ids if i in incidents]

    # --- crime rows (powers the table + the map) ---
    crime_rows = [
        {
            "id": c["id"],
            "crime_type": c.get("crime_type", ""),
            "crime_head": c.get("crime_head", ""),
            "ipc_section": c.get("ipc_section", ""),
            "severity": c.get("severity", "Medium"),
            "district": c.get("district", ""),
            "datetime": c.get("datetime", ""),
            "status": c.get("status", ""),
            "mo_tags": c.get("mo_tags", ""),
            "weapon": c.get("weapon", "No"),
            "lat": float(c["lat"]) if c.get("lat") else None,
            "lon": float(c["lon"]) if c.get("lon") else None,
        }
        for c in crimes
    ]
    crime_rows.sort(key=lambda r: r["datetime"], reverse=True)

    # --- stats ---
    dates = sorted(c["datetime"] for c in crimes if c.get("datetime"))
    districts = sorted({c.get("district", "") for c in crimes if c.get("district")})
    crime_types = Counter(c.get("crime_type", "") for c in crimes)
    severities = Counter(c.get("severity", "Medium") for c in crimes)
    weapon_used = sum(1 for c in crimes if c.get("weapon") == "Yes")
    cleared = sum(1 for c in crimes if c.get("status") in CLEARED)

    # --- associates (co-offenders by shared incidents) ---
    by_incident = _offenders_by_incident()
    adj = _adjacency(by_incident)
    # top shared crime per associate
    shared_crimes: dict[str, Counter] = defaultdict(Counter)
    for iid in offender_ids:
        co = [o for o in by_incident.get(iid, []) if o != person_id]
        ctype = incidents.get(iid, {}).get("crime_type", "")
        for o in co:
            shared_crimes[o][ctype] += 1
    associates = []
    for pid, shared in adj[person_id].most_common():
        top_shared = shared_crimes[pid].most_common(1)
        associates.append({
            "person_id": pid,
            "name": persons.get(pid, {}).get("name", pid),
            "gender": persons.get(pid, {}).get("gender", "M"),
            "shared": shared,
            "top_shared_crime": top_shared[0][0] if top_shared else "",
        })

    # --- timeline (monthly) ---
    months = Counter(c["datetime"][:7] for c in crimes if len(c.get("datetime", "")) >= 7)
    timeline = [{"month": m, "count": months[m]} for m in sorted(months)]

    # --- threat heuristic (transparent) ---
    sev_points = sum(SEVERITY_WEIGHT.get(c.get("severity", "Medium"), 2) for c in crimes)
    threshold = _recent_month()
    recent = sum(v for m, v in months.items() if m >= threshold)
    weapon_ratio = weapon_used / len(crimes) if crimes else 0
    raw = sev_points * 1.4 + recent * 3 + weapon_ratio * 25
    threat_score = max(0, min(100, round(raw)))
    threat_level = "High" if threat_score >= 66 else "Medium" if threat_score >= 33 else "Low"

    return {
        "person": {
            "id": person["id"],
            "name": person.get("name", person_id),
            "age": int(person["age"]) if str(person.get("age", "")).isdigit() else None,
            "age_group": person.get("age_group", ""),
            "gender": person.get("gender", "M"),
            "address_district": person.get("address_district", ""),
            "role": person.get("role", ""),
        },
        "stats": {
            "total_incidents": len(crimes),
            "as_victim": len(victim_ids),
            "first_seen": dates[0] if dates else None,
            "last_seen": dates[-1] if dates else None,
            "districts": districts,
            "co_offenders": len(adj[person_id]),
            "clearance_rate": round(cleared / len(crimes) * 100, 1) if crimes else 0,
            "weapon_incidents": weapon_used,
            "top_crime": crime_types.most_common(1)[0][0] if crime_types else None,
        },
        "threat": {"score": threat_score, "level": threat_level},
        "crimes": crime_rows,
        "timeline": timeline,
        "crime_mix": {
            "by_type": [{"name": k, "count": v} for k, v in crime_types.most_common()],
            "by_severity": [{"name": k, "count": v} for k, v in severities.most_common()],
        },
        "top_mo": [
            {"name": k, "count": v}
            for k, v in Counter(
                t for c in crimes for t in c.get("mo_tags", "").split("|") if t
            ).most_common(8)
        ],
        "associates": associates,
    }


@router.get("/relationship/{a}/{b}")
def relationship(a: str, b: str):
    """The shared FIRs that link two people (the 'how they're connected' detail)."""
    incidents = {r["id"]: r for r in get_store().rows("incidents")}
    a_ids = set(_person_incident_ids(a, "offender"))
    b_ids = set(_person_incident_ids(b, "offender"))
    shared_ids = a_ids & b_ids
    shared = [
        {
            "id": incidents[i]["id"],
            "crime_type": incidents[i].get("crime_type", ""),
            "severity": incidents[i].get("severity", "Medium"),
            "district": incidents[i].get("district", ""),
            "datetime": incidents[i].get("datetime", ""),
            "status": incidents[i].get("status", ""),
        }
        for i in shared_ids
        if i in incidents
    ]
    shared.sort(key=lambda r: r["datetime"], reverse=True)
    return {"a": a, "b": b, "shared": shared}


def _recent_month() -> str:
    """YYYY-MM threshold ~90 days ago, for the recency component of the threat score."""
    from datetime import datetime, timedelta

    return (datetime.now() - timedelta(days=90)).strftime("%Y-%m")
