# CLAUDE.md

Guidance for working in this repository.

## What this is

An **AI-driven crime analytics & visualization platform** for the Karnataka State Police (KSP) / State Crime Records Bureau (SCRB), built as a hackathon submission that **must be deployed on Zoho Catalyst**. It replaces Excel silos with interactive geospatial dashboards, criminological network/link analysis, and AI-driven predictive/anomaly intelligence.

Authoritative design docs (read these before large changes):
- `challange.md` — the problem statement (do not edit).
- `Police_FIR_ER_Diagram.pdf` + `ERD_SCHEMA.md` — the official FIR database schema provided
  with the challenge. **The data model must strictly follow it** (table & column names
  exactly as transcribed in `ERD_SCHEMA.md`). Do not edit the PDF.
- `zoho_resources.md` — Catalyst service mapping; "use the matching Catalyst service" is a hard rule (do not edit).
- `project_tech_stack.md` — the locked stack, constraints, data model, and phased build plan.

## Architecture in one picture

```
React SPA (Slate) ──HTTPS──> API Gateway ──> FastAPI app (AppSail, Python)
                                                    │  reads only precomputed aggregates
                                                    ▼
                                               Data Store  <── Cron/Event Functions (heavy precompute)
                                               Stratus (files/PDF), Cache
QuickML (LLM+RAG) · Zia AutoML · Zia Services · SmartBrowz are called from the API / jobs.
Maps (MapLibre + OSM) and the graph (Cytoscape.js) render client-side — Catalyst has no map/graph service.
```

### The one pattern that governs everything: **precompute-and-serve**
Heavy math (DBSCAN hotspot clustering, networkx centrality + Louvain community detection, heuristic + KMeans risk tiering, z-score + IsolationForest anomaly detection) runs in **Cron/Event Functions** (15-min limit) and writes compact rows to *aggregate tables* (`hotspot_cells`, `district_stats`, `risk_scores`, `trend_baselines`, `anomalies`, `alerts`, `graph_edges`, `communities`). The **FastAPI request path only reads those aggregates** — never compute heavy work in a request handler. This is why we respect the two hard Catalyst limits below.

## Hard constraints — do not violate
- **Data Store: max 300 rows per query.** Always paginate; serve precomputed aggregates, not raw scans.
- **Function/request timeout: 30s** on the API path; Cron/Event jobs get 15 min — put heavy work there.
- **Budget = $250 Catalyst credit, ~60-day window.** The one undisclosed cost is **QuickML LLM/RAG**: every LLM call goes through the single interface in `backend/app/services/llm.py`; keep prompts small; tear endpoints down when idle.
- **Compliance:** when a Catalyst service exists for a capability (see `zoho_resources.md`), use it — not a 3rd-party substitute. Maps/graph rendering are the documented exceptions (no Catalyst equivalent).

## Repo layout

```
backend/
  app/
    main.py            FastAPI app entrypoint (uvicorn app.main:app)
    config.py          Settings: DATA_MODE=local|catalyst, paths, QuickML config
    routers/           One router per pillar: health, cases, hotspots, network, predictive,
                       analytics, alerts, assistant, report
    services/
      datastore.py     Raw table access. Local mode reads data/output/<Table>.csv; catalyst mode uses the SDK.
      firdata.py       ERD joins: cached denormalised case view + entity-resolved accused index.
                       Routers read these views, never raw tables directly.
      llm.py           THE gate for all LLM calls (QuickML provider + mock provider).
functions/             Cron/Event serverless jobs (Phase 1+). Each subfolder = one function.
frontend/
  src/
    lib/api.ts         Typed API client (talks to the backend).
    components/Layout.tsx
    pages/             One page per pillar.
data/
  generator/generate_synthetic.py   Synthetic Police FIR dataset per the ERD (stdlib only).
  output/                            Generated CSVs, one per ERD table (gitignored).
```

## Commands

```powershell
# Data
python data/generator/generate_synthetic.py --cases 20000 --seed 42

# Backend (local dev: serves the generated CSVs, no Catalyst needed)
cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 9000      # /health, /docs

# Frontend
cd frontend; npm install; npm run dev           # http://localhost:5173

# Catalyst
catalyst login; catalyst init; catalyst deploy
```

## Conventions
- **Backend:** Python 3.9+ (AppSail-compatible — avoid 3.10+-only syntax in shipped code). FastAPI + Pydantic models for every response. New analytical endpoints read aggregate tables only.
- **New heavy computation** → add a job under `functions/`, write results to an aggregate table, then expose a thin read endpoint. Never inline it in a request handler.
- **Memoise with `@cached` from `app/services/cache.py`, never `functools.lru_cache`.** `lru_cache` releases its lock across the wrapped call, so the ~12 concurrent requests a page opens with each recompute the same thing. Then add the new cache to the warm set in `app/warmup.py` so a restarted container fills it before a user asks. See `docs/KEEPWARM.md`.
- **All LLM/RAG access** goes through `backend/app/services/llm.py`. Do not import an LLM SDK anywhere else.
- **Data access** goes through `backend/app/services/datastore.py` so local (CSV) and Catalyst (SDK) modes stay interchangeable.
- **Frontend:** React function components + hooks, TanStack Query for server state, Tailwind for styling. Maps = MapLibre GL JS, graph = Cytoscape.js, charts = Recharts.
- **Secrets** via env vars only (`.env`, gitignored; see `.env.example`). Never commit a Catalyst `project_id` or keys.

## Data model (see `ERD_SCHEMA.md` — strict, from the official FIR ERD)
Core (26 ERD tables): `CaseMaster` hub + party tables (`ComplainantDetails`, `Victim`,
`Accused`, `ArrestSurrender`, `ChargesheetDetails`, `ActSectionAssociation`), legal masters
(`Act`, `Section`, `CrimeHead`, `CrimeSubHead`, `CrimeHeadActSection`), lookups
(`CaseCategory`, `GravityOffence`, `CaseStatusMaster`, `CasteMaster`, `ReligionMaster`,
`OccupationMaster`), and organisation (`State`, `District`, `Unit`, `UnitType`, `Rank`,
`Designation`, `Employee`, `Court`).
Precomputed by jobs: `graph_edges`, `communities`, `hotspot_cells`, `district_stats`, `risk_scores`, `trend_baselines`, `anomalies`, `alerts`.
Accused identity across FIRs is resolved analytics-side by (AccusedName, GenderID) — never add columns to the ERD tables.

## Build phases (current: Phase 3–4 — feature-complete demo, hardening in progress)
0. Foundation: scaffold, deploy skeletons, synthetic data. ✅ done (auth still outstanding — tracked separately).
1. Geospatial hotspots ✅ · 2. Network/link analysis ✅ · 3. Predictive & anomaly AI ✅ (heuristic; QuickML/AutoML swap-in in progress)
4. NL query + AI reports ✅ (mock LLM by default; QuickML wiring in progress) · 5. Polish ← we are here
All four analytical pillars are demoable end-to-end locally. Remaining gaps before this matches the phase-0 doc's original plan: role-based auth, real ML models behind the heuristic endpoints (Phase 2 items below), and wiring the precompute-and-serve read path in catalyst mode. Full original detail in `project_tech_stack.md` §6.
