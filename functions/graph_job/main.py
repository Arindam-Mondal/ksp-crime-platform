"""
Cron / Event job — network precompute.

Reads the `Accused` table, resolves identities by (AccusedName, GenderID), builds
co-accused `graph_edges` (weight = shared FIRs), augments them with networkx degree
centrality, runs Louvain community detection to group offenders into actual clusters
(not just pairwise links — the "reveal organized crime structures" ask), then writes
`graph_edges` and `communities`. Can run nightly (Cron) or react to Accused inserts
(Event/Signal).

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
    accused = io.read_all("Accused")
    edges = agg.graph_edges(accused)
    communities: list[dict] = []

    try:
        import networkx as nx
        g = nx.Graph()
        for e in edges:
            g.add_edge(e["src_person"], e["dst_person"], weight=e["weight"])

        # centrality (degree) via networkx — written onto each edge's endpoints for the UI
        deg = nx.degree_centrality(g) if g.number_of_nodes() else {}
        for e in edges:
            e["src_centrality"] = round(deg.get(e["src_person"], 0), 4)
            e["dst_centrality"] = round(deg.get(e["dst_person"], 0), 4)

        # Louvain community detection — genuine clustering over the whole graph, not
        # just one offender's ego neighborhood.
        if g.number_of_nodes():
            # resolution tuned to produce cohesive cells rather than one giant weakly-
            # connected mega-component — see firdata.communities() for the rationale.
            raw = nx.community.louvain_communities(g, weight="weight", seed=42, resolution=12.0)
            for cid, members in enumerate(raw):
                if len(members) < 3:
                    continue
                communities.append({"id": cid, "size": len(members),
                                    "members": "|".join(sorted(members))})
    except Exception as exc:  # pragma: no cover
        print(f"[graph_job] centrality/community detection skipped: {exc}")

    written = {
        "graph_edges": io.replace_table("graph_edges", edges),
        "communities": io.replace_table("communities", communities),
    }
    print(f"[graph_job] wrote {written}")
    return {"status": "ok", "written": written}
