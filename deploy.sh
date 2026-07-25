#!/usr/bin/env bash
#
# End-to-end deploy of the KSP Crime Intelligence Platform to Zoho Catalyst.
# Portable: macOS, Linux, or Windows Git-Bash. (Windows-native alternative: deploy.ps1)
#
# Pipeline (each step logged; every external command echoed before it runs):
#   1. Preflight   - Docker daemon, Catalyst CLI login, node
#   2. Data        - regenerate the synthetic ERD dataset, bundle CSVs into the image context
#   3. Backend     - buildx -> OCI-layout tar -> `catalyst deploy appsail --source docker-archive://`
#                    (the ONLY image path Catalyst's bundle creator accepts from an older Docker
#                     engine; `docker://` fails server-side with "Parse manifest data ... expected u32")
#   4. Activation  - poll live /health until its build_id matches this build
#                    (Catalyst activates asynchronously and silently keeps the old build on failure)
#   5. Frontend    - npm build with the prod API base, refresh client/, deploy web client
#   6. Verify      - smoke-check the key live endpoints (incl. socio-economic + MO), URLs
#
# Backend + frontend are rebuilt from source every run, so the latest code always ships:
# the Dockerfile `COPY app ./app` bundles all backend code + app/data/*.csv (the Census
# reference), and Vite compiles the current frontend. The AppSail container runs
# DATA_MODE=local (bundled CSVs), so the FastAPI app computes every aggregate — including
# the new per-capita + MO analytics — on the fly. The functions/ Cron jobs are NOT deployed
# here; they are scaffolding for the future catalyst-mode Data Store architecture, dormant
# while DATA_MODE=local.
#
# Usage:
#   ./deploy.sh                    # full end-to-end deploy
#   ./deploy.sh --skip-data        # reuse existing data/output CSVs
#   ./deploy.sh --skip-frontend    # backend only
#   ./deploy.sh --skip-backend     # frontend only
#   ./deploy.sh --cases 30000 --seed 7

set -euo pipefail

API_URL="https://ksp-api-50043111658.development.catalystappsail.in"
FRONTEND_URL="https://ksp-crime-platform-60072978366.development.catalystserverless.in/app/"
OCI_TAR="ksp-api-oci.tar"
BUILD_ID="$(date +%Y%m%d-%H%M%S)"
CASES=20000
SEED=42
SKIP_DATA=0 SKIP_BACKEND=0 SKIP_FRONTEND=0

while [ $# -gt 0 ]; do
  case "$1" in
    --skip-data)     SKIP_DATA=1 ;;
    --skip-backend)  SKIP_BACKEND=1 ;;
    --skip-frontend) SKIP_FRONTEND=1 ;;
    --cases)         CASES="$2"; shift ;;
    --seed)          SEED="$2"; shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

cd "$(dirname "$0")"

log()  { printf '  [%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
step() { printf '\n\033[36m=== [%s] %s ===\033[0m\n' "$(date +%H:%M:%S)" "$*"; }
run()  { printf '  \033[33m> %s\033[0m\n' "$*"; "$@"; }   # echo the command, then execute it

# Python launcher: py (Windows), else python3, else python.
if command -v py >/dev/null 2>&1; then PY=py
elif command -v python3 >/dev/null 2>&1; then PY=python3
else PY=python; fi

echo "KSP Crime Platform - Catalyst deploy (build id: $BUILD_ID)"

# ---------------------------------------------------------------- 1. preflight
step "Preflight checks"
# NOTE: `docker info` exits 0 even when the daemon is down; `docker version` does not.
run docker version --format 'docker engine {{.Server.Version}}'
run catalyst whoami
run node --version
if [ "$SKIP_FRONTEND" -eq 0 ]; then
  if [ ! -f frontend/.env.production ]; then
    echo "ERROR: frontend/.env.production missing - it must contain VITE_API_BASE=$API_URL" >&2
    exit 1
  fi
  log "frontend/.env.production: $(head -1 frontend/.env.production)"
fi

# ---------------------------------------------------------------- 2. data
if [ "$SKIP_DATA" -eq 0 ]; then
  step "Generate synthetic ERD dataset ($CASES cases, seed $SEED)"
  run "$PY" data/generator/generate_synthetic.py --cases "$CASES" --seed "$SEED"
  log "Bundling the 26 ERD CSVs into the Docker build context (backend/_seed_data)"
  rm -f backend/_seed_data/*.csv
  cp data/output/*.csv backend/_seed_data/
  log "CSVs bundled: $(ls backend/_seed_data/*.csv | wc -l | tr -d ' ')"
else
  step "Data generation SKIPPED (--skip-data); using existing backend/_seed_data"
fi

# ---------------------------------------------------------------- 3. backend
if [ "$SKIP_BACKEND" -eq 0 ]; then
  step "Build backend image as an OCI-layout archive (buildx container driver)"
  # Catalyst's bundle creator only parses OCI-layout tars. Older Docker engines'
  # `docker save` (used by the CLI's docker:// source) emits legacy docker-layout tars,
  # so we build the OCI archive ourselves and upload it verbatim via docker-archive://.
  if ! docker buildx inspect ocibuilder >/dev/null 2>&1; then
    run docker buildx create --name ocibuilder --driver docker-container
  fi
  run docker buildx inspect ocibuilder --bootstrap >/dev/null
  log "buildx builder 'ocibuilder' is running"
  run docker buildx build --builder ocibuilder --platform linux/amd64 \
      --build-arg "BUILD_ID=$BUILD_ID" -o "type=oci,dest=$OCI_TAR" -t ksp-api:latest backend
  log "OCI archive: $OCI_TAR ($(du -m "$OCI_TAR" | cut -f1) MB)"

  step "Deploy backend to Catalyst AppSail"
  run catalyst deploy appsail --name ksp-api --source "docker-archive://$OCI_TAR" --port 9000

  step "Wait for Catalyst to activate build $BUILD_ID (up to 6 min)"
  # The CLI reports success on UPLOAD; the build is bundled + activated asynchronously.
  # If bundling fails (console: "Parse manifest data ... expected u32"), the old build
  # silently keeps serving - which is exactly what this poll catches.
  deadline=$(( $(date +%s) + 360 ))
  live=""
  while [ "$(date +%s)" -lt "$deadline" ]; do
    health="$(curl -s --max-time 20 "$API_URL/health" || true)"
    live="$(printf '%s' "$health" | sed -n 's/.*"build_id":"\([^"]*\)".*/\1/p')"
    if [ "$live" = "$BUILD_ID" ]; then break; fi
    log "live build: ${live:-none} - waiting for $BUILD_ID ..."
    sleep 15
  done
  if [ "$live" != "$BUILD_ID" ]; then
    echo "ERROR: activation TIMED OUT - live build is still '${live:-none}'." >&2
    echo "Check the AppSail build log in the Catalyst console (look for 'Parse manifest data');" >&2
    echo "the toggle to enable AppSail is console-only." >&2
    exit 1
  fi
  log "Activated. /health: $health"
else
  step "Backend deploy SKIPPED (--skip-backend)"
fi

# ---------------------------------------------------------------- 4. frontend
if [ "$SKIP_FRONTEND" -eq 0 ]; then
  step "Build frontend (Vite, base /app/, API base from .env.production)"
  ( cd frontend && run npm run build )

  step "Refresh client/ and deploy web client"
  log "Replacing client/ contents with frontend/dist (keeping client-package.json)"
  find client -mindepth 1 -maxdepth 1 ! -name client-package.json -exec rm -rf {} +
  cp -R frontend/dist/. client/
  # SPA deep links: client-package.json routes 404s to 404.html -> serve the app shell.
  cp client/index.html client/404.html
  run catalyst deploy --only client
else
  step "Frontend deploy SKIPPED (--skip-frontend)"
fi

# ---------------------------------------------------------------- 5. verify
step "Verify live endpoints"
for p in /health /api/analytics/summary /api/analytics/case-funnel \
         /api/alerts/spikes /api/hotspots/districts /api/network/top-offenders \
         /api/analytics/socioeconomic /api/predictive/risk-scores; do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$API_URL$p" || echo 000)"
  if [ "$code" = "200" ]; then log "OK   $p"; else log "FAIL $p (HTTP $code)"; fi
done
# Modus Operandi needs a person id, so fetch a live one and confirm the endpoint answers.
offid="$(curl -s --max-time 30 "$API_URL/api/network/top-offenders?limit=1" \
         | sed -n 's/.*"person_id":"\([^"]*\)".*/\1/p' | head -1)"
if [ -n "$offid" ]; then
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$API_URL/api/network/mo/$offid" || echo 000)"
  if [ "$code" = "200" ]; then log "OK   /api/network/mo/$offid"; else log "FAIL /api/network/mo (HTTP $code)"; fi
fi
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$FRONTEND_URL" || echo 000)"
if [ "$code" = "200" ]; then log "OK   frontend"; else log "FAIL frontend (HTTP $code)"; fi

printf '\n\033[32mDeploy complete.\033[0m\n'
echo "  API:      $API_URL  (build $BUILD_ID)"
echo "  Frontend: $FRONTEND_URL"
