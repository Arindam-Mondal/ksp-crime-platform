# KSP Crime Intelligence Platform

AI-driven crime analytics & visualization platform for the Karnataka State Police (KSP) / State Crime Records Bureau (SCRB). Hackathon submission deployed on **Zoho Catalyst**.

> Problem statement: [`challange.md`](./challange.md) · **Official FIR data model: [`ERD_SCHEMA.md`](./ERD_SCHEMA.md)** (from `Police_FIR_ER_Diagram.pdf`, followed strictly) · Tech stack & architecture: [`project_tech_stack.md`](./project_tech_stack.md) · Catalyst services: [`zoho_resources.md`](./zoho_resources.md)

## The four pillars

1. **Geospatial hotspots** — district/station drill-down maps over CaseMaster GPS, spatiotemporal clusters, emerging-trend (spike) alerts.
2. **Network / link analysis** — co-accused graph with cross-FIR identity resolution, repeat-offender profiles with arrest history, association detection.
3. **Predictive & anomaly AI** — district risk scoring (volume, heinous share, pendency), anomaly call-outs.
4. **NL query + AI reports** — plain-English questions over FIR BriefFacts + one-click PDF intelligence reports.

Plus the ERD-powered operational analytics: investigation funnel (FIR → chargesheet → trial →
conviction), act/section usage, arrest & surrender analytics, officer workload, court caseload,
and complainant/victim/accused demographics.

## Repo layout

```
backend/        FastAPI app (uv + Docker) → Catalyst AppSail custom OCI runtime
functions/      Cron/Event serverless jobs (heavy precompute, pip + Python 3.9) → Catalyst Functions
frontend/       React + Vite + TS SPA → Catalyst Slate
data/generator/ Synthetic Police FIR dataset generator per the ERD (stdlib Python, no dependencies)
```

---

## Running locally

### Prerequisites

| Tool | Version | Install |
|---|---|---|
| **uv** | any recent | `winget install astral-sh.uv` or `pip install uv` |
| **Node.js** | 18+ | https://nodejs.org |
| **py launcher** | — | ships with Python on Windows; used to run the stdlib generator |

> **Note:** On this machine `python` resolves to Python 2.7. Use `py` or `uv` for all Python 3 work.

---

### Step 1 — Generate the synthetic dataset

The generator is stdlib-only (no install needed). Run it once; outputs one CSV per ERD table
(26 tables — see `ERD_SCHEMA.md`) to `data/output/`.

```powershell
py data/generator/generate_synthetic.py --cases 20000 --seed 42
```

Expected output:
```
Wrote FIR dataset (20000 cases) to ...\data\output
  Units: 237 | Employees: 1041 | Courts: 62
  Complainants: 20844 | Victims: 19151 | Accused: 21690 (habitual-linked rows: 8069)
  ActSections: 35894 | Arrests: 12056 | Chargesheets: 10918 {'B': 584, 'C': 3343, 'A': 6991}
  Categories: FIR=18188, PAR=743, UDR=690, Zero FIR=379
  Emerging spike: 'Chain Snatching' in Ballari (last 30 days)
```

---

### Step 2 — Start the backend

The backend uses **uv** for dependency management and runs on **Python 3.12**.

```powershell
cd backend

# First time only: create the virtual environment and install dependencies
uv sync

# Start the API server (hot-reload enabled)
uv run uvicorn app.main:app --reload --port 9000
```

Verify it's up:
- **Health check:** http://localhost:9000/health — should return `"cases_loaded": 20000`
- **Interactive API docs:** http://localhost:9000/docs

The backend runs in `DATA_MODE=local` by default, which reads the CSVs from `data/output/`.

---

### Step 3 — Start the frontend

Open a **second terminal** (keep the backend running in the first).

```powershell
cd frontend

# First time only: install npm dependencies
npm install

# Start the dev server
npm run dev
```

Open **http://localhost:5173** in your browser.

Vite proxies all `/api` and `/health` requests to the backend on port 9000, so no CORS issues.

---

### Optional: run the backend as a Docker container

If you want to test the exact image that deploys to Catalyst:

```powershell
# Build the image (from repo root)
docker build -t ksp-api:dev backend

# Run it, mounting the synthetic data in
docker run --rm -p 9000:9000 `
  -e DATA_MODE=local `
  -e DATA_DIR=/data `
  -v "${PWD}\data\output:/data" `
  ksp-api:dev
```

Then start the frontend as in Step 3 — it doesn't care whether the API is running via `uv run` or Docker.

---

### Dependency management (backend)

```powershell
cd backend

uv add <package>          # add a runtime dependency
uv add --dev <package>    # add a dev-only dependency (tests, linting)
uv remove <package>       # remove a dependency
```

Both commands update `pyproject.toml` and `uv.lock` automatically. Commit both files.

---

## Deploy to Catalyst

```powershell
npm i -g zcatalyst-cli      # install the Catalyst CLI (once)
catalyst login
catalyst init               # link this repo to your Catalyst project
catalyst appsail:init       # backend: choose "custom runtime" and point at backend/Dockerfile

# Cron/Event precompute jobs (heavy math → aggregate tables)
catalyst functions:add      # reconcile each functions/<job>/catalyst-config.json
catalyst deploy
```

After the first deploy, seed the Data Store and let the jobs populate the aggregate tables:

```powershell
# create the core + aggregate tables (console schema import), then:
py backend/scripts/seed_datastore.py --data data/output
# run hotspot_job / risk_job / graph_job from the Catalyst console (or wait for their cron)
```

Then flip the backend to read aggregates: set `DATA_MODE=catalyst` (and, once QuickML
early-access is on, `LLM_PROVIDER=quickml` + `QUICKML_ENDPOINT`/key) in the AppSail env.
Local dev stays on `DATA_MODE=local` / `LLM_PROVIDER=mock` (no Catalyst needed).

> The Catalyst code paths (`CatalystStore` ZCQL, `QuickMLProvider`, SmartBrowz PDF, and the
> `functions/` jobs) are written deploy-ready but can only be validated in a live Catalyst
> project — see `functions/README.md` for the per-job deploy notes.

See [`CLAUDE.md`](./CLAUDE.md) for the full architecture, conventions, and the phased build plan.
