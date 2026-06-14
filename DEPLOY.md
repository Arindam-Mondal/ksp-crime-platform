# Deploying to Zoho Catalyst — runbook

Goes from "account, no project" to a **live backend + frontend**, then connects the
**real QuickML model**, then (phase 2) the Data Store + Cron Functions.

Legend: 🧑 = you run it (interactive / needs your account); 🤖 = already prepared in the repo.
Tip: run the 🧑 shell steps from this session with a leading `!` so the output lands here.

---

## 0. Prerequisites
- ✅ Zoho Catalyst account (you have one).
- ✅ Node 18+ (you have v24).
- **Docker Desktop running** — required to build the backend image (the daemon was off when I checked; start it before step 3).
- 🤖 Repo is deploy-ready: `backend/Dockerfile` (bundles data), `backend/app-config.json`, `catalyst.json`, the `functions/` jobs, and `frontend/dist`.

## 1. Install the CLI + log in   🧑
```powershell
npm i -g zcatalyst-cli
catalyst login        # opens a browser; pick the same DC/region as your Zoho account
```

## 2. Create + link the project   🧑
1. In the **Catalyst console** (console.catalyst.zoho.com) → **Create Project** → name it `ksp-crime-platform`. Copy its **Project ID**.
2. Link this repo:
```powershell
catalyst init         # select the existing project; enable AppSail + Functions + Client hosting
```
This writes the real `project_id` into `catalyst.json` (it's `0` now — never commit a real one to a shared repo).

---

## 3. Deploy the backend (AppSail, custom Docker)   🧑
The image is **Python 3.12 + uv**, and bundles the synthetic CSVs so the live API has data immediately in `DATA_MODE=local` (phase 1).

```powershell
# 3a. Bundle the dataset into the image build context (one-time / whenever data changes)
py data/generator/generate_synthetic.py --incidents 20000 --seed 42
Copy-Item data/output/*.csv backend/_seed_data/

# 3b. (recommended) verify the image locally first — needs Docker Desktop running
docker build -t ksp-api:test backend
docker run --rm -p 9000:9000 ksp-api:test
#   → in another shell: curl http://localhost:9000/health   (expect incidents_loaded: 20000)

# 3c. deploy to AppSail
catalyst appsail:init     # choose "custom runtime" → point at backend/Dockerfile, port 9000
catalyst deploy           # or: catalyst appsail:deploy
```
AppSail prints the **API URL** (e.g. `https://ksp-crime-platform-<id>.development.catalystserverless.com`). Save it — the frontend needs it.

> Verified for you: `uv.lock` resolves the new deps (`httpx`, `zcatalyst-sdk`) and the backend imports clean. Not verifiable here: the live AppSail build/run (needs your project).

## 4. Deploy the frontend (Web Client Hosting)   🧑
The SPA must call the AppSail API by absolute URL in production (no Vite proxy live).

```powershell
cd frontend
# point the build at the API URL from step 3c:
"VITE_API_BASE=https://<your-api-url>" | Out-File -Encoding utf8 .env.production
npm install ; npm run build      # outputs frontend/dist

# add a web client via the CLI and serve dist:
catalyst init                    # if not already added: choose "Client" → set the serve dir to frontend/dist
catalyst deploy
```
**SPA routing gotcha:** the app uses client-side routes (`/network`, `/person/:id`, …). Configure the hosting to serve `index.html` for unknown paths (404-fallback / URL-rewrite to `/index.html`) — set it in the client config or the console, or react-router deep links will 404.

**CORS:** the API already allows `localhost:5173`. Add your hosted frontend origin to `cors_origins` in `backend/app/config.py` (or set it via env) and redeploy the backend.

## 5. Smoke test (live)   🧑
- Open the hosted frontend URL → Dashboard loads, alerts feed populates, map renders.
- `curl https://<api-url>/health` → `incidents_loaded: 20000`.
- Walk Hotspots / Network / Predictive / Reports / Ask the Data.

At this point **backend + frontend are live** (mock LLM). Now connect the real model.

---

## 6. Enable QuickML + connect the real model   🧑  ← what you asked about
QuickML LLM Serving is the **Catalyst-compliant** model path (keeps you inside the rules + credits).

1. **Enable / request access.** In the console → your project → **QuickML** (under AI/ML).
   If it's gated, use the in-console **"Request early access"** for *LLM Serving*; it's approved per-account. (This is the one budget unknown — pricing is undisclosed, so spin it up only for dev/demo and **tear it down when idle**.)
2. **Deploy a serving model.** QuickML → **LLM Serving** → **Deploy/Serve a model** → pick **Qwen 2.5 14B Instruct** (matches `QUICKML_MODEL`). Wait for it to reach *Running*.
3. **Grab the connection details** the console shows for the deployed endpoint:
   - **Inference endpoint URL** → `QUICKML_ENDPOINT`
   - **API key / auth token** → `QUICKML_API_KEY`
   - **Model name** → `QUICKML_MODEL` (e.g. `qwen2.5-14b-instruct`)
4. **Wire it** — set these on the **AppSail** service env (console → AppSail → Configuration → Environment), then redeploy:
   ```
   LLM_PROVIDER=quickml
   QUICKML_ENDPOINT=<inference url>
   QUICKML_API_KEY=<key>
   QUICKML_MODEL=qwen2.5-14b-instruct
   ```
   The single gate `backend/app/services/llm.py::QuickMLProvider` already does the HTTP call.
5. **Test it.**
   - Locally first (fastest loop): put the four vars in `backend/.env`, run the API, then
     `curl -X POST localhost:9000/api/assistant/ask -H "Content-Type: application/json" -d '{"question":"Which districts have rising chain snatching?"}'` — `provider` should come back `quickml` with a real answer, and `/api/report` narratives become real.
   - Then the same against the live API URL.

> ⚠️ Contract check: `QuickMLProvider.complete()` is written to the common OpenAI-style
> chat shape (`messages[]` → `choices[0].message.content`). If your QuickML endpoint expects
> a different request/response shape, that one method is the only thing to adjust — share the
> endpoint's sample request and I'll align it. Keep `LLM_PROVIDER=mock` as the safe fallback.

---

## 7. Phase 2 — Data Store + Cron Functions (move off bundled CSVs)
Once you want the precompute-and-serve architecture live:
1. **Create tables** (console → Data Store): the four core tables + the aggregates
   (`hotspot_cells, district_stats, trend_baselines, alerts, risk_scores, anomalies, graph_edges`).
2. **Seed** the core tables from the CSVs (admin creds):
   ```powershell
   py backend/scripts/seed_datastore.py --data data/output
   ```
3. **Deploy the Cron jobs** and run them once to populate the aggregates:
   ```powershell
   catalyst functions:add        # reconcile each functions/<job>/catalyst-config.json
   catalyst deploy
   #   then run hotspot_job / risk_job / graph_job from the console (or wait for cron)
   ```
   Remember to vendor `functions/common/` into each job folder (or use a shared layer) — see `functions/README.md`.
4. **Flip the API** to read aggregates: set `DATA_MODE=catalyst` on the AppSail env and redeploy.
   (Optional: enable SmartBrowz + Stratus for server-side report PDFs via `SMARTBROWZ_ENDPOINT`/`STRATUS_BUCKET`.)

## 8. Budget guardrails ($250 / ~60 days)
- AppSail + Functions stay within the free tier at demo scale; static frontend is negligible.
- **QuickML is the cost unknown** — keep prompts small (already done), and **stop/undeploy the serving model when not demoing**.
- Check the console **Billing/Usage** after each phase.

---

### What's prepared vs. what's yours
- 🤖 Prepared & verified locally: deps resolve (`uv.lock`), frontend builds with `VITE_API_BASE`, Dockerfile bundles data, all feature endpoints work in `local`/`mock` mode, function compute verified on the CSVs.
- 🧑 Yours (interactive / account-gated, can't be verified from here): `catalyst login`, project creation, AppSail/Client deploy, QuickML enablement + endpoint, and the live smoke tests above.
- 🔌 One code touch-point may need your input: the exact QuickML request/response shape (step 6 ⚠️).
