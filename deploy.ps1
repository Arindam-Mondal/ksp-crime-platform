<#
.SYNOPSIS
  End-to-end deploy of the KSP Crime Intelligence Platform to Zoho Catalyst.

.DESCRIPTION
  Runs the whole pipeline with step-by-step logging, printing every external
  command before it executes:

    1. Preflight   - Docker daemon, Catalyst CLI login, node/npm
    2. Data        - regenerate the synthetic ERD dataset, bundle CSVs into the image context
    3. Backend     - buildx -> OCI-layout tar -> `catalyst deploy appsail --source docker-archive://`
                     (the ONLY image path Catalyst's bundle creator accepts from this machine;
                      `docker://` fails server-side with "Parse manifest data ... expected u32")
    4. Activation  - poll the live /health until its build_id matches this build
                     (Catalyst activates asynchronously and silently keeps the old build on failure)
    5. Frontend    - npm build with the prod API base, refresh client/, deploy web client
    6. Verify      - smoke-check the key live endpoints, print the URLs

.EXAMPLE
  .\deploy.ps1                    # full end-to-end deploy
  .\deploy.ps1 -SkipData          # reuse existing data/output CSVs
  .\deploy.ps1 -SkipFrontend      # backend only
  .\deploy.ps1 -SkipBackend       # frontend only
#>
[CmdletBinding()]
param(
    [switch]$SkipData,
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [int]$Cases = 20000,
    [int]$Seed = 42
)

$ErrorActionPreference = "Stop"
$RepoRoot    = $PSScriptRoot
$ApiUrl      = "https://ksp-api-50043111658.development.catalystappsail.in"
$FrontendUrl = "https://ksp-crime-platform-60072978366.development.catalystserverless.in/app/"
$OciTar      = "ksp-api-oci.tar"
$BuildId     = Get-Date -Format "yyyyMMdd-HHmmss"

function Log([string]$msg) {
    Write-Host ("  [{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg)
}
function Step([string]$msg) {
    Write-Host ""
    Write-Host ("=== [{0}] {1} ===" -f (Get-Date -Format "HH:mm:ss"), $msg) -ForegroundColor Cyan
}
function Run([string]$cmd) {
    # Print the exact command, then run it - so the log doubles as a manual runbook.
    Write-Host ("  > {0}" -f $cmd) -ForegroundColor Yellow
    Invoke-Expression $cmd
    if ($LASTEXITCODE -ne 0) { throw "Command failed (exit $LASTEXITCODE): $cmd" }
}

Set-Location $RepoRoot
Write-Host "KSP Crime Platform - Catalyst deploy (build id: $BuildId)" -ForegroundColor Green

# ---------------------------------------------------------------- 1. preflight
Step "Preflight checks"
Run 'docker info --format "docker engine {{.ServerVersion}}"'
Run 'catalyst whoami'
Run 'node --version'
if (-not $SkipFrontend) {
    if (-not (Test-Path "frontend/.env.production")) {
        throw "frontend/.env.production missing - it must contain VITE_API_BASE=$ApiUrl"
    }
    Log ("frontend/.env.production: " + (Get-Content frontend/.env.production -TotalCount 1))
}

# ---------------------------------------------------------------- 2. data
if (-not $SkipData) {
    Step "Generate synthetic ERD dataset ($Cases cases, seed $Seed)"
    Run "py data/generator/generate_synthetic.py --cases $Cases --seed $Seed"
    Log "Bundling the 26 ERD CSVs into the Docker build context (backend/_seed_data)"
    Remove-Item backend/_seed_data/*.csv -Force -ErrorAction SilentlyContinue
    Copy-Item data/output/*.csv backend/_seed_data/
    Log ("CSVs bundled: " + (Get-ChildItem backend/_seed_data/*.csv).Count)
} else {
    Step "Data generation SKIPPED (-SkipData); using existing backend/_seed_data"
}

# ---------------------------------------------------------------- 3. backend
if (-not $SkipBackend) {
    Step "Build backend image as an OCI-layout archive (buildx container driver)"
    # Catalyst's bundle creator only parses OCI-layout tars. This engine's `docker save`
    # (used by the CLI's docker:// source) emits legacy docker-layout tars, so we build
    # the OCI archive ourselves and upload it verbatim via docker-archive://.
    $builderOk = $false
    try { docker buildx inspect ocibuilder *> $null; $builderOk = ($LASTEXITCODE -eq 0) } catch {}
    if (-not $builderOk) {
        Run 'docker buildx create --name ocibuilder --driver docker-container'
    }
    # NOTE: don't pipe this through Select-Object -First N — early pipeline termination
    # makes PowerShell 5.1 report exit -1 for the native command.
    Run 'docker buildx inspect ocibuilder --bootstrap *> $null'
    Log "buildx builder 'ocibuilder' is running"
    Run "docker buildx build --builder ocibuilder --platform linux/amd64 --build-arg BUILD_ID=$BuildId -o type=oci,dest=$OciTar -t ksp-api:latest backend"
    Log ("OCI archive: {0} ({1:N0} MB)" -f $OciTar, ((Get-Item $OciTar).Length / 1MB))

    Step "Deploy backend to Catalyst AppSail"
    Run "catalyst deploy appsail --name ksp-api --source docker-archive://$OciTar --port 9000"

    Step "Wait for Catalyst to activate build $BuildId (up to 6 min)"
    # The CLI reports success on UPLOAD; the build is bundled + activated asynchronously.
    # If bundling fails (console: "Parse manifest data ... expected u32"), the old build
    # silently keeps serving - which is exactly what this poll catches.
    $deadline = (Get-Date).AddMinutes(6)
    $live = $null
    while ((Get-Date) -lt $deadline) {
        try { $h = Invoke-RestMethod "$ApiUrl/health" -TimeoutSec 20 } catch { $h = $null }
        if ($h) { $live = $h.build_id }
        if ($live -eq $BuildId) { break }
        Log "live build: $live - waiting for $BuildId ..."
        Start-Sleep -Seconds 15
    }
    if ($live -ne $BuildId) {
        throw ("Activation TIMED OUT - live build is still '$live'. Check the AppSail build log " +
               "in the Catalyst console (look for 'Parse manifest data'); the toggle to enable " +
               "AppSail is console-only.")
    }
    Log "Activated. /health: cases_loaded=$($h.cases_loaded), data_mode=$($h.data_mode), build_id=$($h.build_id)"
} else {
    Step "Backend deploy SKIPPED (-SkipBackend)"
}

# ---------------------------------------------------------------- 4. frontend
if (-not $SkipFrontend) {
    Step "Build frontend (Vite, base /app/, API base from .env.production)"
    Push-Location frontend
    try { Run 'npm run build' } finally { Pop-Location }

    Step "Refresh client/ and deploy web client"
    Log "Replacing client/ contents with frontend/dist (keeping client-package.json)"
    Get-ChildItem client -Exclude client-package.json | Remove-Item -Recurse -Force
    Copy-Item frontend/dist/* client/ -Recurse
    # SPA deep links: client-package.json routes 404s to 404.html -> serve the app shell.
    Copy-Item client/index.html client/404.html
    Run 'catalyst deploy --only client'
} else {
    Step "Frontend deploy SKIPPED (-SkipFrontend)"
}

# ---------------------------------------------------------------- 5. verify
Step "Verify live endpoints"
$checks = @("/health", "/api/analytics/summary", "/api/analytics/case-funnel",
            "/api/alerts/spikes", "/api/hotspots/districts", "/api/network/top-offenders")
foreach ($p in $checks) {
    try {
        $r = Invoke-WebRequest -UseBasicParsing "$ApiUrl$p" -TimeoutSec 30
        Log ("OK  {0}  ({1} bytes)" -f $p, $r.Content.Length)
    } catch {
        Log ("FAIL {0}  {1}" -f $p, $_.Exception.Message)
    }
}
try {
    $r = Invoke-WebRequest -UseBasicParsing $FrontendUrl -TimeoutSec 30
    Log ("OK  frontend  ({0} bytes)" -f $r.Content.Length)
} catch {
    Log ("FAIL frontend  {0}" -f $_.Exception.Message)
}

Write-Host ""
Write-Host "Deploy complete." -ForegroundColor Green
Write-Host "  API:      $ApiUrl  (build $BuildId)"
Write-Host "  Frontend: $FrontendUrl"
