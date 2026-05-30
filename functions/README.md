# Catalyst Functions — heavy precompute (Phase 1+)

These are the **Cron / Event** serverless jobs that implement the *precompute-and-serve*
pattern (see `../CLAUDE.md`). They run the heavy math (15-min limit) and write compact
rows into aggregate tables that the FastAPI API then just SELECTs.

Planned jobs (added as each phase lands):

| Phase | Function | Trigger | Reads | Writes |
| --- | --- | --- | --- | --- |
| 1 | `hotspot_job` | Cron (nightly) | `incidents` | `hotspot_cells`, `district_stats`, `trend_baselines`, `alerts` |
| 2 | `graph_job` | Cron / Event on insert | `incidents`, `incident_persons` | `graph_edges` |
| 3 | `risk_job` | Cron | `incidents`, `locations` | `risk_scores`, `anomalies` |

Each job lives in its own subfolder with a `catalyst-config.json` (created via
`catalyst functions:add`). Heavy libs (`pandas`, `scikit-learn`, `networkx`) are
allowed here — this is where they belong, not on the API request path.
