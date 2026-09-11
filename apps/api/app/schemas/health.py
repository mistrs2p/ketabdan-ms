"""Health API schemas (Task 5.9; docs/06 §4, docs/01 §10).

``LivenessRead`` and ``ReadinessRead`` document the exact bodies the
health endpoints already return — they add no behavior, only the typed
contract for OpenAPI. Check values are the fixed words the endpoints
emit (``ok`` / ``unavailable`` / ``no_recent_heartbeat``); failure
responses never carry URLs, credentials, or exception text.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LivenessRead(BaseModel):
    """Liveness body — ``GET /api/health`` and ``GET /api/health/live``."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"status": "ok"}]}
    )

    status: Literal["ok"] = Field(
        description="Always `ok` — liveness never checks dependencies."
    )


class ReadinessChecks(BaseModel):
    """Per-dependency results inside the readiness body."""

    database: Literal["ok", "unavailable"] = Field(
        description="One `SELECT 1` on the app's engine (bounded timeout)."
    )
    redis: Literal["ok", "unavailable"] = Field(
        description="One `PING` with bounded socket timeouts."
    )
    worker: Literal["ok", "no_recent_heartbeat"] = Field(
        description="Informational only: whether a notification worker "
        "process has a live arq heartbeat key in Redis. Never gates the "
        "overall status."
    )


class ReadinessRead(BaseModel):
    """Readiness body — ``GET /api/health/ready`` (503 when not ready)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "ok",
                    "checks": {
                        "database": "ok",
                        "redis": "ok",
                        "worker": "ok",
                    },
                }
            ]
        }
    )

    status: Literal["ok", "not_ready"] = Field(
        description="`ok` only when both database and redis are `ok`."
    )
    checks: ReadinessChecks = Field(
        description="Per-dependency results (worker is informational)."
    )
