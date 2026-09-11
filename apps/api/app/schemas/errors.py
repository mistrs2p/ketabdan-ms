"""Error API schemas (docs/06 §4b).

``ErrorDetail`` is the error body the API actually produces for
non-validation failures (401 authentication, 403 authorization, 404
not-found) — the exact shape locked by tests/test_api_error_policy.py:
a JSON object with a single ``detail`` string.

It exists only so routes can reference one accurate schema in their
OpenAPI ``responses`` declarations. Validation failures (422) are
different — ``detail`` is Pydantic's structured list there — and stay
documented by FastAPI's built-in validation-error schema, not by this
model.
"""

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """The body of a 401 / 403 / 404 error response (docs/06 §4b)."""

    detail: str


def error_response(description: str, *, example_detail: str) -> dict[str, Any]:
    """Build one OpenAPI ``responses`` entry for the error contract.

    Routes document their non-success statuses declaratively, e.g.
    ``responses={401: error_response("...", example_detail="Not authenticated")}``.
    The explicit ``content`` (schema $ref + example) is required because
    FastAPI uses a provided ``content`` verbatim and would otherwise
    drop the ``model``-derived schema. Pure documentation — nothing
    here runs at request time.
    """

    return {
        "model": ErrorDetail,  # registers the component in #/components/schemas
        "description": description,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorDetail"},
                "example": {"detail": example_detail},
            }
        },
    }
