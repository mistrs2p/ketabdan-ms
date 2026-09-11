"""JSON job serialization for the arq queue (Task 5.7).

arq's default job serializer is **pickle**; storing pickles in Redis means
a compromised Redis can execute arbitrary code in the worker on
deserialization. We replace it with strict JSON — which also enforces the
"stable, serializable data only" contract by construction: anything that
is not JSON-serializable fails loudly at enqueue time instead of silently
entering the queue.

One deliberate exception: arq stores the *exception object* of a failed
job as the job result, so the serializer must be able to render
exceptions. They become ``"TypeName: message"`` strings — and since every
exception the notification layer raises is already guaranteed token-free
and free of raw provider responses (docs/01 §6), that text is safe to
store. Every other non-JSON value still raises.

The pair must be used on BOTH sides (the enqueueing pool and the worker) —
both take it from this module.
"""

import json
from typing import Any

from arq.jobs import Deserializer, Serializer


def _render_exception(value: object) -> str:
    return f"{type(value).__name__}: {value}"


def _json_default(value: object) -> str:
    # Exceptions (failed-job results) render as sanitized strings; see
    # the module docstring. Anything else is a contract violation and
    # must fail loudly.
    if isinstance(value, BaseException):
        return _render_exception(value)
    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )


def json_job_serializer(data: dict[str, Any]) -> bytes:
    """Serialize an arq job (or failed-job result) dict to UTF-8 JSON.

    Non-serializable values raise — except exception results, which
    render as ``"TypeName: message"`` (token-free by construction).
    """
    return json.dumps(data, ensure_ascii=False, default=_json_default).encode(
        "utf-8"
    )


def json_job_deserializer(data: bytes) -> dict[str, Any]:
    """Deserialize an arq job/result dict from UTF-8 JSON."""
    return json.loads(data.decode("utf-8"))
