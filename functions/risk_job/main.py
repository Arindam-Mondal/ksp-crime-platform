"""
Cron job — predictive risk + anomaly precompute.

Builds the case view from the ERD tables and writes `risk_scores` and `anomalies`.
The heuristic risk score stands in for Zia AutoML (swap in the AutoML inference here
once a model is trained — keep training out of the hot loop per the budget guardrail
in CLAUDE.md).

Deploy note: package `common/` with this function. Not runnable locally.
"""
from __future__ import annotations

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from common import aggregations as agg          # noqa: E402
from common import catalyst_io as io            # noqa: E402
from common import firview                      # noqa: E402
from common import reference                    # noqa: E402


def handler(event, context):
    cases = firview.build_case_view(io.read_all)
    socio = reference.socioeconomic()
    written = {
        "risk_scores": io.replace_table("risk_scores", agg.risk_scores(cases, socio)),
        "anomalies": io.replace_table("anomalies", agg.anomalies(cases, top_n=50)),
    }
    print(f"[risk_job] wrote {written}")
    return {"status": "ok", "written": written}
