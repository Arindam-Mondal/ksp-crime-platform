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
backend/        FastAPI app (uv + Docker) → Catalyst AppSail custom OCI runtime
functions/      Cron/Event serverless jobs (heavy precompute, pip + Python 3.9) → Catalyst Functions
frontend/       React + Vite + TS SPA → Catalyst Slate
data/generator/ Synthetic Karnataka dataset generator (stdlib Python, no dependencies)
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

The generator is stdlib-only (no install needed). Run it once; outputs four CSVs to `data/output/`.

```powershell
py data/generator/generate_synthetic.py --incidents 20000 --seed 42
```

Expected output:
```
Wrote synthetic dataset to ...\data\output
  locations.csv            182 rows
  persons.csv             6000 rows  (324 repeat offenders)
  incidents.csv          20000 rows
  incident_persons.csv   46566 rows
  emerging-trend spike seeded: 'Chain Snatching' in Raichur (last 30 days)
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
- **Health check:** http://localhost:9000/health — should return `"incidents_loaded": 20000`
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
catalyst deploy
```

See [`CLAUDE.md`](./CLAUDE.md) for the full architecture, conventions, and the phased build plan.
