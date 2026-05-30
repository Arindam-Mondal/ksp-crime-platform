"""
Pillar 2 — network / link analysis.

Production: serve the precomputed `graph_edges` table (networkx centrality computed
by a Cron/Event job). Phase 0 scaffold: build a small co-offender ego-graph from
`incident_persons` on the fly so the Cytoscape view has something to render.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter, HTTPException

from app.services.datastore import get_store

router = APIRouter(prefix="/api/network", tags=["network"])


def _offenders_by_incident() -> dict[str, list[str]]:
    links = get_store().rows("incident_persons")
    by_incident: dict[str, list[str]] = defaultdict(list)
    for l in links:
        if l.get("role") == "offender":
            by_incident[l["incident_id"]].append(l["person_id"])
    return by_incident


@router.get("/top-offenders")
def top_offenders(limit: int = 20):
    """Repeat offenders ranked by incident count."""
    links = get_store().rows("incident_persons")
    counts = Counter(l["person_id"] for l in links if l.get("role") == "offender")
    persons = {p["id"]: p for p in get_store().rows("persons")}
    items = [
        {"person_id": pid, "name": persons.get(pid, {}).get("name", pid), "incidents": n}
        for pid, n in counts.most_common(limit)
    ]
    return {"items": items}


@router.get("/ego/{person_id}")
def ego_graph(person_id: str, depth: int = 1):
    """Co-offender graph around a person (nodes + edges for Cytoscape)."""
    by_incident = _offenders_by_incident()
    persons = {p["id"]: p for p in get_store().rows("persons")}
    if person_id not in persons:
        raise HTTPException(status_code=404, detail="person not found")

    # adjacency: two offenders linked if they share an incident
    adj: dict[str, Counter] = defaultdict(Counter)
    for offenders in by_incident.values():
        for i in range(len(offenders)):
            for j in range(i + 1, len(offenders)):
                a, b = offenders[i], offenders[j]
                adj[a][b] += 1
                adj[b][a] += 1

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

    nodes = [{"id": pid, "name": persons.get(pid, {}).get("name", pid)} for pid in seen]
    # de-dup undirected edges
    uniq = {tuple(sorted((e["source"], e["target"]))): e for e in edges}
    return {"root": person_id, "nodes": nodes, "edges": list(uniq.values())}
