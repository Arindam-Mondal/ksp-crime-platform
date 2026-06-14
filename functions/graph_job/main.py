"""
Cron / Event job — network precompute.

Reads `incident_persons`, builds co-offender `graph_edges` (weight = shared incidents)
and augments nodes with networkx centrality, then writes the `graph_edges` table.
Can run nightly (Cron) or react to incident_persons inserts (Event/Signal).

Deploy note: package `common/` with this function; `networkx` is in requirements.txt.
Not runnable locally.
"""
from __future__ import annotations

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from common import aggregations as agg          # noqa: E402
from common import catalyst_io as io            # noqa: E402


def handler(event, context):
    links = io.read_all("incident_persons")
    edges = agg.graph_edges(links)

    # centrality (degree) via networkx — written onto each edge's endpoints for the UI
    try:
        import networkx as nx
        g = nx.Graph()
        for e in edges:
            g.add_edge(e["src_person"], e["dst_person"], weight=e["weight"])
        deg = nx.degree_centrality(g) if g.number_of_nodes() else {}
        for e in edges:
            e["src_centrality"] = round(deg.get(e["src_person"], 0), 4)
            e["dst_centrality"] = round(deg.get(e["dst_person"], 0), 4)
    except Exception as exc:  # pragma: no cover
        print(f"[graph_job] centrality skipped: {exc}")

    written = io.replace_table("graph_edges", edges)
    print(f"[graph_job] wrote graph_edges={written}")
    return {"status": "ok", "written": {"graph_edges": written}}
