# Backend — FastAPI on Catalyst AppSail

Single Python service. Reads **only precomputed aggregates** in production (see `../CLAUDE.md`).

## Local dev

```powershell
# from repo root, generate data first (use the py launcher -> Python 3):
py data/generator/generate_synthetic.py --incidents 20000 --seed 42

cd backend
py -3 -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 9000
```

- Health: http://localhost:9000/health
- Interactive docs: http://localhost:9000/docs
- Local mode reads `../data/output/*.csv` (`DATA_MODE=local`, the default).

> Note: on this machine `python` is Python 2.7 — always use `py` / `py -3` for Python 3.

## Layout
- `app/main.py` — app + router wiring.
- `app/config.py` — settings (`DATA_MODE`, `LLM_PROVIDER`, QuickML config).
- `app/routers/` — one router per pillar (`health`, `incidents`, `hotspots`, `network`, `predictive`, `assistant`).
- `app/services/datastore.py` — local-CSV / Catalyst-Data-Store switch.
- `app/services/llm.py` — the single LLM gate (mock / QuickML).

## Deploy to AppSail
`app-config.json` is a starting point — run the CLI to initialise/validate it against your project:

```powershell
catalyst appsail:init     # reconciles app-config.json (stack, command, port)
catalyst deploy           # or: catalyst appsail:deploy
```

Notes:
- AppSail injects the listen port via env (`X_ZOHO_CATALYST_LISTEN_PORT`); the start command honours it.
- Set `DATA_MODE=catalyst` in the AppSail env once `CatalystStore` (ZCQL) is wired in `datastore.py`.
- Keep `LLM_PROVIDER=mock` until QuickML early-access is confirmed (budget guardrail).
