"""
Cron job (nightly) — geospatial precompute.

Builds the denormalised case view from the ERD tables (CaseMaster + lookups) and
writes the aggregate tables the API serves: hotspot_cells, district_stats,
trend_baselines, alerts.

Deploy note: `common/` (firview + aggregations + catalyst_io) must be packaged with
this function (vendor it into the folder or use a shared layer). Not runnable locally —
needs a Catalyst Function context. Reconcile catalyst-config.json via `catalyst functions:add`.
"""
from __future__ import annotations

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))  # for `common`
from common import aggregations as agg          # noqa: E402
from common import catalyst_io as io            # noqa: E402
from common import firview                      # noqa: E402


def handler(event, context):  # Catalyst Cron entry point
    cases = firview.build_case_view(io.read_all)

    written = {
        "hotspot_cells": io.replace_table("hotspot_cells", agg.hotspot_cells(cases)),
        "district_stats": io.replace_table("district_stats", agg.district_stats(cases)),
        "trend_baselines": io.replace_table("trend_baselines", agg.trend_baselines(cases)),
        "alerts": io.replace_table("alerts", agg.spike_alerts(cases)),
    }
    print(f"[hotspot_job] wrote {written}")
    return {"status": "ok", "written": written}
