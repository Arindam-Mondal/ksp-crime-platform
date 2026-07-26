"""
Cron job — predictive risk + anomaly precompute.

Builds the case view from the ERD tables and writes `risk_scores` and `anomalies`.
`risk_scores` combines the transparent heuristic (primary rank, unchanged) with an
unsupervised KMeans `ml_tier` — a genuine scikit-learn signal, and the honest
alternative to a fabricated supervised model when no labeled outcomes exist yet
(swap in real Zia AutoML inference here once they do). `anomalies` combines the
z-score checks with IsolationForest multivariate detection — keep training/inference
out of the request hot path per the budget guardrail in CLAUDE.md; both run here only.

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
    anomalies = agg.anomalies(cases, top_n=50) + agg.multivariate_anomalies(cases, top_n=20)
    anomalies.sort(key=lambda a: abs(a["z"]), reverse=True)
    written = {
        "risk_scores": io.replace_table("risk_scores", agg.risk_scores(cases, socio)),
        "anomalies": io.replace_table("anomalies", anomalies),
    }
    print(f"[risk_job] wrote {written}")
    return {"status": "ok", "written": written}
