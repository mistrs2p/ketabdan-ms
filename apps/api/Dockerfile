# Production image for the Ketabdaneh API (Task 5.11; docs/01 §12).
#
# Multi-stage: dependencies (and nothing else) are installed into a venv in
# the build stage; the runtime stage copies the venv plus the application
# source — no pip cache, no build toolchain, no tests, no dev dependency
# group (only [project].dependencies from pyproject.toml is installed).
#
# The same image also runs the ARQ notification worker (docker-compose
# .prod.yml overrides the command with `python -m app.worker`) and Alembic
# migrations (`... run --rm api alembic upgrade head`) — the worker is part
# of the same Python application and needs the identical dependency set, so
# one image with different commands is the honest topology, not an
# artificial abstraction.
#
# Build context: apps/api/ (see .dockerignore). No secrets are baked in —
# every credential is injected at runtime via environment variables
# (Task 5.10; docs/01 §11).

# syntax=docker/dockerfile:1

# ---- build stage: install dependencies into a clean venv --------------------
FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# venv at a stable path so the runtime stage can copy it as-is (the venv's
# entry points hard-code /opt/venv/bin/python — keep the path identical).
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip

# Install the application's [project].dependencies (pyproject.toml is the
# single dependency source). Installing the project itself is a side effect
# and harmless — the runtime stage runs from the source tree.
COPY pyproject.toml ./
COPY app ./app
RUN pip install .

# ---- runtime stage -----------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Non-root runtime user.
RUN useradd --create-home --uid 1000 app

WORKDIR /srv

COPY --from=build /opt/venv /opt/venv

# Application source, migrations, and the worker container healthcheck.
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini pyproject.toml worker_healthcheck.py ./

USER app

# The API listens on 0.0.0.0:8000 by default; the published HOST port is
# mapped in docker-compose.prod.yml.
EXPOSE 8000

# Production ASGI server — no --reload, no watchers, no debug flags. The
# host/port honor the application's own API_HOST/API_PORT settings
# (defaults match the EXPOSE above); shell form so the env vars apply.
CMD ["sh", "-c", "uvicorn app.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000}"]
