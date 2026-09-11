import app.models  # noqa: F401 — registers all ORM models on Base.metadata
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.event_assignments import router as event_assignments_router
from app.api.events import router as events_router
from app.api.health import metrics_router, router as health_router
from app.api.middleware import RequestLoggingMiddleware
from app.api.persons import router as persons_router
from app.api.roles import router as roles_router
from app.core.config import get_settings
from app.core.logging import configure_logging

# Configure application logging once per process, before anything logs
# (Task 5.8). Under uvicorn this runs at app-import time — AFTER uvicorn's
# own dictConfig — so our root handler/format wins. No app-level Exception
# handler is registered on purpose: Starlette's ServerErrorMiddleware
# re-raises unhandled exceptions and the server logs the single stack
# trace; the API error contract ({"detail": ...}) stays exactly as-is.
_settings = get_settings()
configure_logging(level=_settings.log_level)

app = FastAPI(title="Ketabdaneh API")

# Browser clients (the web app's client-side auth and business calls,
# Phase 5.3) are cross-origin in development (frontend :3000, API :8000).
# Allowed origins come from settings (CORS_ALLOW_ORIGINS) — never a
# wildcard with credentials.
if _settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origins_list,
        allow_credentials=False,  # auth is a Bearer header, not cookies
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

# One request log line per HTTP call: method, path, status, duration,
# request id (Task 5.8; uvicorn's own access log is disabled by
# app.core.logging so requests are logged exactly once).
app.add_middleware(RequestLoggingMiddleware)

app.include_router(auth_router)
app.include_router(roles_router)
app.include_router(persons_router)
app.include_router(events_router)
app.include_router(event_assignments_router)

# Health (liveness / readiness — Task 5.9) and the Prometheus metrics
# endpoint. Both public by design: health checks and infrastructure
# scraping must work independently of auth (docs/06 §4, docs/01 §10).
app.include_router(health_router)
app.include_router(metrics_router)
