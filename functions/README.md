# Catalyst Functions — heavy precompute (Phase 1+)

These are the **Cron / Event** serverless jobs that implement the *precompute-and-serve*
pattern (see `../CLAUDE.md`). They run the heavy math (15-min limit) and write compact
rows into aggregate tables that the FastAPI API then just SELECTs.

Jobs (scaffolded — code complete, validate config + SDK calls at deploy):

| Phase | Function | Trigger | Reads (ERD tables) | Writes |
| --- | --- | --- | --- | --- |
| 1 | `hotspot_job` | Cron (nightly) | `CaseMaster` + lookups (via `common/firview.py`) | `hotspot_cells`, `district_stats`, `trend_baselines`, `alerts` |
| 2 | `graph_job` | Cron / Event on insert | `Accused` (identities resolved by name+gender) | `graph_edges` (+ networkx centrality) |
| 3 | `risk_job` | Cron | `CaseMaster` + lookups (via `common/firview.py`) | `risk_scores`, `anomalies` |

Each job is a subfolder with `main.py` (handler `main.handler`), `catalyst-config.json`,
and `requirements.txt`. Shared, framework-free compute lives in `common/aggregations.py`
(a superset mirror of `backend/app/services/aggregations.py` — **keep them in sync**);
`common/firview.py` joins the ERD tables into the denormalised case view (mirror of
`backend/app/services/firdata.py`); `common/catalyst_io.py` does the Data Store
read/replace via ZCQL.

**Deploy notes**
- `common/` must be packaged with each function (vendor it into the folder or use a
  Catalyst shared layer); each `main.py` adds `../` to `sys.path` to import it.
- The `catalyst-config.json` files are starter scaffolds — reconcile each against your
  project with `catalyst functions:add` (the CLI owns the canonical schema).
- Validate the `zcatalyst_sdk` call shapes in `common/catalyst_io.py` against the
  installed SDK version. For full-table reads at scale, prefer the Data Store **bulk
  read** job over the ZCQL paging used here.
- Heavy libs (`scikit-learn`, `networkx`) belong here, not on the API request path.
