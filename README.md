# KSP Crime Intelligence Platform

AI-driven crime analytics & visualization platform for the Karnataka State Police (KSP) / State Crime Records Bureau (SCRB). Hackathon submission deployed on **Zoho Catalyst**.

> Problem statement: [`challange.md`](./challange.md) · Tech stack & architecture: [`project_tech_stack.md`](./project_tech_stack.md) · Catalyst services: [`zoho_resources.md`](./zoho_resources.md)

## The four pillars

1. **Geospatial hotspots** — district drill-down maps, spatiotemporal clusters, emerging-trend (spike) alerts.
2. **Network / link analysis** — suspect↔victim↔location graph, repeat-offender & MO tracking, association detection.
3. **Predictive & anomaly AI** — risk scoring, socio-economic overlays, anomaly call-outs.
4. **NL query + AI reports** — plain-English questions over the data + one-click PDF intelligence reports.

## Repo layout

```
backend/        FastAPI app  → Catalyst AppSail (managed Python runtime)
functions/      Cron/Event serverless jobs (heavy precompute) → Catalyst Functions
frontend/       React + Vite + TS SPA → Catalyst Slate
data/generator/ Synthetic Karnataka dataset generator (stdlib Python)
```

Architecture detail and the **precompute-and-serve** pattern live in [`project_tech_stack.md`](./project_tech_stack.md) and [`CLAUDE.md`](./CLAUDE.md).

## Quick start (local dev)

Prereqs: Python 3.9+ and Node 18+.

```powershell
# 1. Generate the synthetic dataset (writes CSVs to data/output/)
python data/generator/generate_synthetic.py --incidents 20000 --seed 42

# 2. Backend (serves the CSVs in local/dev mode)
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 9000
#   → http://localhost:9000/health   http://localhost:9000/docs

# 3. Frontend
cd ..\frontend
npm install
npm run dev
#   → http://localhost:5173  (proxies /server to the backend)
```

## Deploy to Catalyst (Phase 0)

```powershell
npm i -g zcatalyst-cli      # Catalyst CLI
catalyst login
catalyst init               # link this folder to your Catalyst project
# backend → AppSail, frontend → Slate, functions → Functions
catalyst deploy
```

See [`CLAUDE.md`](./CLAUDE.md) for the full command reference and conventions.
