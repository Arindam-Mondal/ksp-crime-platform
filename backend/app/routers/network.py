"""
Pillar 2 — criminological network / link analysis + person intelligence.

Built on the entity-resolved accused index (services/firdata.offenders()): Accused
rows are per-case in the ERD, so the same physical person across FIRs is resolved by
(name, gender) — mirroring real name-based entity resolution on FIR data.

Precompute-and-serve scoping note: unlike hotspots/predictive/alerts (see
datastore.read_aggregate_or_compute), the endpoints here stay on live compute even in
catalyst mode. `graph_edges` and `communities` ARE precomputed by graph_job, but every
endpoint here needs a *derived, per-request slice* of the graph (one person's ego
network, a ranked top-N, cluster membership joined back to case counts) rather than a
flat table serve — wiring that correctly means rebuilding co_accused_adjacency() from
the small graph_edges table instead of the full case view, which touches offenders(),
mo.py, and every route below. Left as a follow-up rather than risking an unverified
half-wiring (this whole path is already unrunnable/untestable locally either way)."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from app.services import aggregations, firdata, mo

router = APIRouter(prefix="/api/network", tags=["network"])


@router.get("/top-offenders")
def top_offenders(limit: int = 20):
    """Repeat offenders (resolved identities) ranked by linked FIR count."""
    off = firdata.offenders()["by_id"]
    adj = firdata.co_accused_adjacency()
    community_of = firdata.communities()["by_person"]
    items = []
    for oid, g in off.items():
        if g["n_cases"] < 2:
            break  # by_id is ordered by case count
        items.append({
            "person_id": oid,
            "name": g["name"],
            "gender": g["gender"],
            "cases": g["n_cases"],
            "arrests": g["arrests"] + g["surrenders"],
            "districts": len(g["districts"]),
            "associates": len(adj.get(oid, {})),
            "community_id": community_of.get(oid),
        })
        if len(items) >= limit:
            break
    return {"items": items}


@router.get("/ego/{person_id}")
def ego_graph(person_id: str, depth: int = 1):
    """Co-accused graph around a person (nodes + edges for the force graph)."""
    off = firdata.offenders()["by_id"]
    if person_id not in off:
        raise HTTPException(status_code=404, detail="person not found")
    adj = firdata.co_accused_adjacency()

    frontier = {person_id}
    seen = {person_id}
    edges = []
    for _ in range(max(1, depth)):
        nxt = set()
        for node in frontier:
            for neighbor, weight in adj.get(node, {}).items():
                edges.append({"source": node, "target": neighbor, "weight": weight})
                if neighbor not in seen:
                    seen.add(neighbor)
                    nxt.add(neighbor)
        frontier = nxt

    community_of = firdata.communities()["by_person"]
    nodes = [
        {
            "id": oid,
            "name": off[oid]["name"],
            "gender": off[oid]["gender"],
            "cases": off[oid]["n_cases"],
            "is_root": oid == person_id,
            "community_id": community_of.get(oid),
        }
        for oid in seen
    ]
    uniq = {tuple(sorted((e["source"], e["target"]))): e for e in edges}
    return {"root": person_id, "nodes": nodes, "edges": list(uniq.values())}


@router.get("/person/{person_id}")
def person_profile(person_id: str):
    """Self-contained briefing: identity, stats, threat, linked FIRs, arrest history,
    sections invoked, timeline, and ranked associates."""
    off = firdata.offenders()
    g = off["by_id"].get(person_id)
    if not g:
        raise HTTPException(status_code=404, detail="person not found")
    cidx = firdata.case_index()
    arr_by_accused = firdata.arrests()["by_accused"]
    adj = firdata.co_accused_adjacency()

    crimes = [cidx[c] for c in g["case_ids"] if c in cidx]
    crimes.sort(key=lambda c: c["incident"], reverse=True)
    crime_rows = [
        {
            "id": c["id"], "crime_no": c["crime_no"], "sub_head": c["sub_head"],
            "head": c["head"], "gravity": c["gravity"], "sections": c["sections"],
            "district": c["district"], "station": c["station"],
            "datetime": c["incident"], "status": c["status"], "cstype": c["cstype"],
            "lat": c["lat"], "lon": c["lon"],
        }
        for c in crimes
    ]

    dates = sorted(c["incident"] for c in crimes if c["incident"])
    sub_counts = Counter(c["sub_head"] for c in crimes)
    head_counts = Counter(c["head"] for c in crimes)
    heinous = sum(1 for c in crimes if c["heinous"])
    charged = sum(1 for c in crimes if c["cstype"] == "A")
    finals = sum(1 for c in crimes if c["cstype"])

    # arrest history from this identity's accused rows
    arrest_events = []
    for arid in g["accused_row_ids"]:
        ev = arr_by_accused.get(arid)
        if ev:
            c = cidx.get(ev["case_id"], {})
            arrest_events.append({
                "date": ev["date"], "type": ev["type"], "district": ev["district"],
                "state": ev["state"], "crime_no": c.get("crime_no", ""),
                "sub_head": c.get("sub_head", ""),
            })
    arrest_events.sort(key=lambda a: a["date"], reverse=True)

    # associates (shared cases via resolved co-accused graph)
    shared_subs: dict[str, Counter] = defaultdict(Counter)
    for cid in g["case_ids"]:
        co = [o for o in off["by_case"].get(cid, []) if o != person_id]
        sub = cidx.get(cid, {}).get("sub_head", "")
        for o in co:
            shared_subs[o][sub] += 1
    associates = []
    for oid, shared in sorted(adj.get(person_id, {}).items(), key=lambda kv: -kv[1]):
        top_shared = shared_subs[oid].most_common(1)
        other = off["by_id"][oid]
        associates.append({
            "person_id": oid, "name": other["name"], "gender": other["gender"],
            "shared": shared, "top_shared_crime": top_shared[0][0] if top_shared else "",
        })

    months = Counter(c["incident"][:7] for c in crimes if len(c["incident"]) >= 7)
    timeline = [{"month": m, "count": months[m]} for m in sorted(months)]

    sections = Counter(s for c in crimes for s in c["sections"])

    # threat heuristic (transparent): gravity mix + recency + arrest pressure
    # Recency is measured against the latest incident in the data, not the wall clock —
    # every other recency window in the app uses that reference, and on a dataset whose
    # last incident predates today the wall clock silently zeroes this term for everyone.
    recent_cut = (aggregations._ref_now(firdata.cases())
                  - timedelta(days=90)).strftime("%Y-%m")
    recent = sum(v for m, v in months.items() if m >= recent_cut)
    raw = heinous * 9 + (len(crimes) - heinous) * 2.5 + recent * 6 + len(adj.get(person_id, {})) * 2
    threat_score = max(0, min(100, round(raw)))
    threat_level = "High" if threat_score >= 66 else "Medium" if threat_score >= 33 else "Low"

    ages = sorted(g["ages"])
    return {
        "person": {
            "id": person_id,
            "name": g["name"],
            "gender": g["gender"],
            "age": ages[-1] if ages else None,
            "districts": g["districts"],
        },
        "stats": {
            "total_cases": len(crimes),
            "heinous_cases": heinous,
            "first_seen": dates[0] if dates else None,
            "last_seen": dates[-1] if dates else None,
            "districts": g["districts"],
            "co_accused": len(adj.get(person_id, {})),
            "arrests": g["arrests"],
            "surrenders": g["surrenders"],
            "chargesheet_rate": round(charged / finals * 100, 1) if finals else 0,
            "top_crime": sub_counts.most_common(1)[0][0] if sub_counts else None,
        },
        "threat": {"score": threat_score, "level": threat_level},
        "crimes": crime_rows,
        "arrest_history": arrest_events,
        "timeline": timeline,
        "crime_mix": {
            "by_type": [{"name": k, "count": v} for k, v in sub_counts.most_common()],
            "by_head": [{"name": k, "count": v} for k, v in head_counts.most_common()],
        },
        "top_sections": [{"name": k, "count": v} for k, v in sections.most_common(8)],
        "associates": associates,
    }


@router.get("/mo/{person_id}")
def modus_operandi(person_id: str, limit: int = 8):
    """Behavioural MO signature for an offender + ranked 'same MO' matches — the recurring
    method surfacing across jurisdictions (see services/mo.py)."""
    if person_id not in firdata.offenders()["by_id"]:
        raise HTTPException(status_code=404, detail="person not found")
    return mo.profile(person_id, limit=limit)


@router.get("/communities")
def communities(limit: int = 15):
    """Organized-crime-structure detection: Louvain community clusters over the full
    co-accused graph (networkx), not just one offender's direct ego links — this is
    the "reveal organized crime structures" ask, answered as actual offender groups
    rather than pairwise connections."""
    data = firdata.communities()
    return {"clusters": data["clusters"][:limit], "total_clusters": len(data["clusters"])}


@router.get("/relationship/{a}/{b}")
def relationship(a: str, b: str):
    """The shared FIRs that link two people (the 'how they're connected' detail)."""
    off = firdata.offenders()["by_id"]
    if a not in off or b not in off:
        raise HTTPException(status_code=404, detail="person not found")
    cidx = firdata.case_index()
    shared_ids = set(off[a]["case_ids"]) & set(off[b]["case_ids"])
    shared = [
        {
            "id": cid, "crime_no": cidx[cid]["crime_no"], "sub_head": cidx[cid]["sub_head"],
            "gravity": cidx[cid]["gravity"], "district": cidx[cid]["district"],
            "datetime": cidx[cid]["incident"], "status": cidx[cid]["status"],
        }
        for cid in shared_ids if cid in cidx
    ]
    shared.sort(key=lambda r: r["datetime"], reverse=True)
    return {"a": a, "b": b, "shared": shared}
