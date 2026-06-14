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
ENV PATH="/app/.venv/bin:$PATH" \
    DATA_MODE=catalyst \
    LLM_PROVIDER=mock \
    PYTHONUNBUFFERED=1
COPY --from=builder /app/.venv /app/.venv
COPY app ./app
EXPOSE 9000
# Catalyst injects the listen port via X_ZOHO_CATALYST_LISTEN_PORT; fall back to 9000 locally.
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${X_ZOHO_CATALYST_LISTEN_PORT:-9000}"]
