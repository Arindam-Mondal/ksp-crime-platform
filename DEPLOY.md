# Deploying KSP Crime Intelligence Platform to Zoho Catalyst

A step-by-step guide from "Catalyst account, no project" to a **live backend + frontend**,
then connecting the **real QuickML model**, then (phase 2) the **Data Store + Cron Functions**.

> Commands/flows here are based on the current Catalyst CLI v1 + AppSail custom-runtime docs
> (see Sources at the bottom). The CLI is interactive — follow its prompts; values in
> `<angle brackets>` are yours to fill in.

**Legend:** 🧑 = you run it (needs your account / interactive) · 🤖 = already prepared in this repo.
In this chat you can prefix a shell step with `!` to run it here and capture the output.

---

## 0 · Prerequisites
| Need | Status |
|---|---|
| Zoho Catalyst account | ✅ you have one |
| Node 18+ | ✅ v24 |
| **Docker Desktop running** | ⚠️ start it — required to build the backend image (was off when I checked) |
| Repo deploy-ready | 🤖 `backend/Dockerfile` (bundles data, honors Catalyst's port), `functions/` jobs, `frontend/dist`, `catalyst.json` |

> **Platform note:** Catalyst custom runtimes accept **OCI images built for `linux/amd64`** only.
> Your Windows machine is x86-64, so a normal `docker build` produces amd64 — fine.

---

## 1 · Install the CLI & log in   🧑
```powershell
npm install -g zcatalyst-cli
catalyst login --dc in        # pick your account's data center: us | eu | in | au | jp | sa | ca
catalyst whoami               # confirms the logged-in email
```
> KSP/Karnataka data usually lives in the **India (`in`)** DC — use the DC your Zoho account was created in.

## 2 · Create & link the project   🧑
1. In the **Catalyst console** (`https://console.catalyst.zoho.com`) → **Create Project** → name it `ksp-crime-platform`.
2. From the repo root, link it:
```powershell
catalyst project:list                 # see your projects + IDs
catalyst init                         # choose "use existing project" → ksp-crime-platform
#   (or, non-interactively:)  catalyst project:use ksp-crime-platform
```
`catalyst.json` gets your real `project_id` (it's `0` in the repo — never commit a real one).

---

## 3 · Deploy the backend (AppSail · custom Docker runtime)   🧑

> **⚡ One-command path:** at the repo root, **`./deploy.sh`** (macOS / Linux / Git-Bash;
> flags `--skip-data`, `--skip-backend`, `--skip-frontend`, `--cases N`, `--seed N`) or
> **`.\deploy.ps1`** (Windows PowerShell; `-SkipData`, `-SkipBackend`, `-SkipFrontend`).
> Both run this section *and* section 4 end-to-end with step-by-step logging — every
> external command is printed before it runs, and activation is verified by matching the
> live `/health` `build_id` against the one baked into the image. The manual steps below
> are what the scripts execute.

The image is **Python 3.12 + uv + gunicorn**; it **bundles the synthetic CSVs** and defaults to
`DATA_MODE=local` so the live API has data immediately (phase 1). It listens on
`$X_ZOHO_CATALYST_LISTEN_PORT` (Catalyst injects this), falling back to 9000.

**3a. Bundle the dataset into the build context** (whenever data changes):
```powershell
py data/generator/generate_synthetic.py --cases 20000 --seed 42
Copy-Item data/output/*.csv backend/_seed_data/
```

**3b. Build the image as an OCI-layout archive** (with Docker Desktop running):
```powershell
docker buildx create --name ocibuilder --driver docker-container   # once per machine
docker buildx build --builder ocibuilder --platform linux/amd64 `
  --build-arg BUILD_ID=$(Get-Date -Format yyyyMMdd-HHmmss) `
  -o type=oci,dest=ksp-api-oci.tar -t ksp-api:latest backend
```
> ⚠️ **Do not use `--source docker://localhost/...`** on an older Docker engine (< Desktop
> 4.12 / no containerd image store): the CLI runs `docker save`, which emits a legacy
> docker-layout tar, and Catalyst's bundle creator rejects it server-side with
> `Parse manifest data: Error("invalid type: map, expected u32")` — while the CLI still
> reports DEPLOYMENT SUCCESSFUL and the old build silently keeps serving. The OCI archive
> above is the format Catalyst actually parses.

**3c. Deploy the archive:**
```powershell
catalyst deploy appsail --name ksp-api --source docker-archive://ksp-api-oci.tar --port 9000
```
> The `docker-archive://` protocol (not shown in `--help`) uploads the tar verbatim. The CLI
> reports success on *upload*; bundling + activation happen asynchronously on Catalyst's side.
> Verify activation via `/health` → its `build_id` must match the `BUILD_ID` you baked in
> (this is exactly what `deploy.ps1` polls for). If it never flips, check the AppSail build
> log in the console — and note the AppSail enable/disable toggle is console-only.

**3d. Set the backend env** (console → **AppSail → ksp-api → Configuration → Environment**):
```
DATA_MODE=local
LLM_PROVIDER=mock
```
Redeploy if you change env. AppSail prints the **API URL**, e.g.
`https://ksp-api-<id>.<dc>.catalystserverless.com` — copy it for step 4.

**3e. Verify:** `curl https://<api-url>/health` → `incidents_loaded: 20000`, and `/docs` loads.

> Verified for you locally: `uv.lock` resolves the new deps (`httpx`, `zcatalyst-sdk`) and the
> backend imports clean. The live AppSail build/run needs your project (can't be tested here).

---

## 4 · Deploy the frontend (Web Client Hosting)   🧑

The SPA must call the API by **absolute URL** in production (no Vite proxy live).

**4a. Build with the API base baked in:**
```powershell
cd frontend
"VITE_API_BASE=https://<api-url-from-3d>" | Out-File -Encoding ascii .env.production
npm install
npm run build                 # → frontend/dist
cd ..
```

**4b. Set up the client folder & drop the build in:**
```powershell
catalyst client:setup         # creates ./client with a client-package.json
Remove-Item client/* -Recurse -Force -Exclude client-package.json
Copy-Item frontend/dist/* client/ -Recurse
```

**4c. Configure `client/client-package.json` for SPA routing.** Set the `404` key to
`index.html` so deep links like `/network` and `/person/:id` serve the app (react-router then
takes over):
```json
{
  "name": "ksp-crime-intelligence",
  "version": "1.0.0",
  "homepage": "index.html",
  "404": "index.html"
}
```

**4d. Deploy & verify:**
```powershell
catalyst deploy client
```
Open the hosted URL → Dashboard loads with the alerts feed, map renders, all pages work.

**4e. CORS:** add your hosted frontend origin to `cors_origins` in `backend/app/config.py`
(or via env), then rebuild + redeploy the backend (step 3). The API already allows `localhost:5173`.

✅ **Backend + frontend are now live** (mock LLM). Continue to connect the real model.

---

## 5 · Enable QuickML & connect the real model   🧑  ← the part you asked about

QuickML LLM Serving is the **Catalyst-compliant** model path (keeps you inside the rules + credits).
All model access already routes through one gate: `backend/app/services/llm.py::QuickMLProvider`.

1. **Enable / request access.** Console → your project → **QuickML** (under AI/ML). If it's gated,
   use the in-console **"Request early access"** for *LLM Serving* (approved per account).
   > 💰 QuickML is the one undisclosed cost — **deploy the model only when demoing and stop it when idle**.
2. **Serve a model.** QuickML → **LLM Serving** → **Deploy / Serve model** → choose
   **Qwen 2.5 14B Instruct** (matches `QUICKML_MODEL`). Wait until status = **Running**.
3. **Copy the connection details** shown for the running endpoint:
   - Inference **endpoint URL** → `QUICKML_ENDPOINT`
   - **API key / token** → `QUICKML_API_KEY`
   - **Model name** → `QUICKML_MODEL` (e.g. `qwen2.5-14b-instruct`)
4. **Wire it on the AppSail env** (console → AppSail → ksp-api → Configuration → Environment), then redeploy:
   ```
   LLM_PROVIDER=quickml
   QUICKML_ENDPOINT=<inference url>
   QUICKML_API_KEY=<key>
   QUICKML_MODEL=qwen2.5-14b-instruct
   ```
5. **Test** (fastest loop is local first — put the 4 vars in `backend/.env`, run the API):
   ```powershell
   curl -X POST http://localhost:9000/api/assistant/ask -H "Content-Type: application/json" `
     -d '{"question":"Which districts have rising chain snatching?"}'
   ```
   Expect `"provider":"quickml"` with a real answer; `/api/report` narratives also become real.
   Then repeat against the live API URL.

> ⚠️ **Contract check.** `QuickMLProvider.complete()` is written to the common OpenAI-style chat
> shape (`messages[]` → `choices[0].message.content`). If your QuickML endpoint expects a
> different request/response shape, **that one method is the only thing to change** — send me a
> sample request/response and I'll align it. `LLM_PROVIDER=mock` stays the safe fallback.

---

## 6 · Phase 2 — Data Store + Cron Functions (precompute-and-serve)

Move off the bundled CSVs to the real architecture (API reads precomputed aggregates).

**6a. Create tables** (console → **Data Store**): the 26 ERD tables (see `ERD_SCHEMA.md` —
table & column names must match exactly) + the aggregates
(`hotspot_cells, district_stats, trend_baselines, alerts, risk_scores, anomalies, graph_edges`).

**6b. Seed the core tables** — use the built-in CLI bulk import, masters first (FK targets),
then case data. One `ds:import` per CSV in `data/output/` (file name = table name), e.g.:
```powershell
# masters
foreach ($t in "State","District","UnitType","Unit","Rank","Designation","Employee",
               "Court","CaseCategory","GravityOffence","CaseStatusMaster","CasteMaster",
               "ReligionMaster","OccupationMaster","CrimeHead","CrimeSubHead",
               "Act","Section","CrimeHeadActSection") {
  catalyst ds:import "data/output/$t.csv" --table $t
}
# case data
foreach ($t in "CaseMaster","ComplainantDetails","Victim","Accused",
               "ActSectionAssociation","ArrestSurrender","ChargesheetDetails") {
  catalyst ds:import "data/output/$t.csv" --table $t
}
```
(`backend/scripts/seed_datastore.py` is an SDK-based alternative if you prefer code.)

**6c. Deploy the Cron jobs** that fill the aggregate tables:
```powershell
catalyst functions:setup          # if the functions dir isn't registered yet
catalyst functions:add            # reconcile each functions/<job>/catalyst-config.json
catalyst deploy functions
```
Then run `hotspot_job`, `risk_job`, `graph_job` once from the console (or wait for their cron) to
populate the aggregates. **Package `functions/common/` into each job folder** (vendor it or use a
shared layer) — see `functions/README.md`.

**6d. Flip the API to read aggregates:** set `DATA_MODE=catalyst` on the AppSail env → redeploy.
(Optional: `SMARTBROWZ_ENDPOINT` + `STRATUS_BUCKET` to render report PDFs server-side.)

---

## 7 · Budget guardrails ($250 / ~60 days)
- AppSail + Functions stay within the free tier at demo scale; static frontend is negligible.
- **QuickML is the cost unknown** — small prompts (already), and **stop the serving model when idle**.
- Watch the console **Billing/Usage** after each phase; tear down endpoints you're not demoing.

---

## What's prepared vs. what's yours
- 🤖 **Prepared & verified locally:** deps resolve (`uv.lock`), frontend builds with `VITE_API_BASE`,
  Dockerfile bundles data + honors `$X_ZOHO_CATALYST_LISTEN_PORT`, all feature endpoints work in
  `local`/`mock` mode, Function compute verified on the CSVs.
- 🧑 **Yours (account-gated, can't run from here):** `catalyst login`, project creation, the
  AppSail/client/functions deploys, Data Store create+import, and QuickML enablement + endpoint.
- 🔌 **May need your input:** the exact QuickML request/response shape (step 5 ⚠️).

## Sources (Catalyst docs)
- [CLI command reference](https://docs.catalyst.zoho.com/en/cli/v1/cli-command-reference/)
- [Deploy AppSail as a custom runtime from the CLI](https://docs.catalyst.zoho.com/en/serverless/help/appsail/custom-runtimes/deploy-from-cli)
- [Deploy AppSail (CLI resources)](https://docs.catalyst.zoho.com/en/cli/v1/deploy-resources/deploy-appsail/)
- [Web Client Hosting](https://docs.catalyst.zoho.com/en/cloud-scale/help/web-client-hosting/introduction/) · [client-package.json](https://docs.catalyst.zoho.com/en/cli/v1/project-directory-structure/client-directory/)
- [AppSail custom runtimes — container registry/protocols](https://docs.catalyst.zoho.com/en/serverless/help/appsail/custom-runtimes/container-registry-services/)
