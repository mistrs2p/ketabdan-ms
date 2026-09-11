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

# OpenAPI tag metadata: one entry per tag the routers actually apply, in
# the order the API is logically read (reference data last is fine —
# Swagger UI orders groups by first appearance, which follows router
# inclusion order below). Tags without an entry here still work; the
# entry only adds the group description shown in Swagger UI / ReDoc.
OPENAPI_TAGS: list[dict[str, str]] = [
    {
        "name": "Authentication",
        "description": (
            "Login and the authenticated identity. Login issues a signed "
            "JWT access token; every other protected endpoint accepts it "
            "as `Authorization: Bearer <token>`."
        ),
    },
    {
        "name": "Roles",
        "description": (
            "Read-only organizational reference data — the six permanent "
            "person roles seeded by migration 0002. No write endpoints."
        ),
    },
    {
        "name": "People",
        "description": (
            "Branch members: listing and creation. Roles are attached at "
            "creation via their stable machine codes."
        ),
    },
    {
        "name": "Events",
        "description": (
            "Events: listing, single reads, and creation. New events "
            "always start in the `DRAFT` status."
        ),
    },
    {
        "name": "Event Assignments",
        "description": (
            "Assignments of people to event responsibilities: listing, "
            "single reads, and creation. New assignments always start "
            "with the `PENDING` approval status."
        ),
    },
    {
        "name": "Health",
        "description": (
            "Public liveness and readiness probes — no authentication, so "
            "infrastructure checks work independently of the app's auth."
        ),
    },
    {
        "name": "Observability",
        "description": (
            "Internal-only observability endpoints (Prometheus metrics). "
            "Meant for infrastructure scraping on an internal network; "
            "protect at the infrastructure level, not via auth."
        ),
    },
]

# Configure application logging once per process, before anything logs
# (Task 5.8). Under uvicorn this runs at app-import time — AFTER uvicorn's
# own dictConfig — so our root handler/format wins. No app-level Exception
# handler is registered on purpose: Starlette's ServerErrorMiddleware
# re-raises unhandled exceptions and the server logs the single stack
# trace; the API error contract ({"detail": ...}) stays exactly as-is.
_settings = get_settings()
configure_logging(level=_settings.log_level)

# OpenAPI metadata (docs/06 §4): the API contract surface exposed at
# /docs (Swagger UI), /redoc, and /openapi.json. The version tracks the
# package version (pyproject.toml) — the API surface grows task by task
# and is currently pre-1.0.
app = FastAPI(
    title="Ketabdaneh API",
    description=(
        "Backend API for **Ketabdaneh**, a branch-management application "
        "for people, events, and event responsibilities.\n\n"
        "### Authentication\n"
        "Obtain a JWT access token via `POST /api/auth/login`, then send "
        "it as `Authorization: Bearer <token>` (use the **Authorize** "
        "button in Swagger UI).\n\n"
        "### Authorization (RBAC)\n"
        "Business endpoints require a permission resolved server-side "
        "from the caller's application roles:\n\n"
        "| Status | Meaning |\n"
        "|---|---|\n"
        "| `401 Unauthorized` | Not authenticated — missing, malformed, "
        "invalid, or expired token, or inactive user |\n"
        "| `403 Forbidden` | Authenticated, but the user lacks the "
        "required permission |\n\n"
        "The 401/403 details are intentionally generic — they never "
        "reveal which check failed.\n\n"
        "### Error contract\n"
        "All errors use the `{\"detail\": ...}` shape. Validation "
        "failures are `422` (structured detail list from Pydantic; "
        "unknown domain reference codes reuse `422` with a plain string "
        "detail); not-found resources are `404`."
    ),
    version="0.1.0",
    openapi_tags=OPENAPI_TAGS,
)

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
