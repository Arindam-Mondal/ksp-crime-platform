# syntax=docker/dockerfile:1
# KSP API — built with uv, deployed as a Catalyst AppSail custom OCI runtime.

# ---- builder: resolve + install deps into /app/.venv ----
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app
# Install deps first (cached layer) from the lockfile, without the project itself.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ---- runtime: slim image with just the venv + app code ----
FROM python:3.12-slim
WORKDIR /app
# Phase 1 default: serve the bundled synthetic CSVs (local mode) so the live API has data
# immediately. Phase 2: set DATA_MODE=catalyst in the AppSail env once the Data Store is
# seeded + the Cron jobs have populated the aggregate tables.
ENV PATH="/app/.venv/bin:$PATH" \
    DATA_MODE=local \
    DATA_DIR=/app/data \
    LLM_PROVIDER=mock \
    PYTHONUNBUFFERED=1
COPY --from=builder /app/.venv /app/.venv
COPY app ./app
# Synthetic dataset bundled into the image. Populate before building:
#   cp data/output/*.csv backend/_seed_data/    (see DEPLOY.md)
COPY _seed_data ./data
EXPOSE 9000
# Catalyst injects the listen port via X_ZOHO_CATALYST_LISTEN_PORT; fall back to 9000 locally.
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${X_ZOHO_CATALYST_LISTEN_PORT:-9000}"]
