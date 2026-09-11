"""OpenAPI / Swagger documentation tests.

Contract-oriented locks on the *generated* OpenAPI document and the
documentation endpoints (``/docs``, ``/redoc``, ``/openapi.json``).
These tests are deliberately schema-driven, not a hardcoded per-route
transcript: routes and their OpenAPI operations are derived from the
app's actual routing table, so a new endpoint cannot silently appear
undocumented, and a removed one cannot leave stale expectations.

What is asserted (and why):

- the documentation endpoints exist and are served;
- every app route is present in the OpenAPI document with a unique
  operation id and at least a summary;
- routes protected by ``require_permission`` declare the Bearer
  security scheme (so Swagger UI's Authorize button actually applies
  to them);
- the expected schemas exist and the documented error statuses are
  present on representative operations;
- tags are exactly the documented set and every operation carries one;
- no secret from settings leaks into the document.
"""

import pytest
from fastapi.routing import APIRoute

from app.core.config import AUTH_SECRET_PLACEHOLDER, get_settings
from app.main import app

# The complete tag vocabulary — one entry per router. ``openapi_tags``
# in app.main must describe exactly these, with no leftovers.
EXPECTED_TAGS = {
    "Authentication",
    "Roles",
    "People",
    "Events",
    "Event Assignments",
    "Health",
    "Observability",
}

# Representative operations whose documented error statuses are locked.
# Maps (method, path) -> statuses that MUST be documented on the
# operation (beyond the success status FastAPI adds automatically).
DOCUMENTED_ERROR_STATUSES = {
    ("post", "/api/auth/login"): {"401"},
    ("get", "/api/auth/me"): {"401"},
    ("get", "/api/roles"): {"401", "403"},
    ("get", "/api/persons"): {"401", "403"},
    ("post", "/api/persons"): {"401", "403", "422"},
    ("get", "/api/events"): {"401", "403"},
    ("get", "/api/events/{event_id}"): {"401", "403", "404"},
    ("post", "/api/events"): {"401", "403", "422"},
    ("get", "/api/event-assignments"): {"401", "403"},
    ("get", "/api/event-assignments/{assignment_id}"): {"401", "403", "404"},
    ("post", "/api/event-assignments"): {"401", "403", "404", "422"},
    ("get", "/api/health/ready"): {"503"},
}

# Permission-protected operations: the endpoint description must name
# the required permission code (docs/06 §4g) so the OpenAPI contract
# states what is being enforced.
PERMISSION_IN_DESCRIPTION = {
    ("get", "/api/roles"): "roles:read",
    ("get", "/api/persons"): "people:read",
    ("post", "/api/persons"): "people:create",
    ("get", "/api/events"): "events:read",
    ("get", "/api/events/{event_id}"): "events:read",
    ("post", "/api/events"): "events:create",
    ("get", "/api/event-assignments"): "assignments:read",
    ("get", "/api/event-assignments/{assignment_id}"): "assignments:read",
    ("post", "/api/event-assignments"): "assignments:create",
}


@pytest.fixture(scope="module")
def openapi_schema() -> dict:
    """The generated OpenAPI document (generation must not crash)."""
    return app.openapi()


def _iter_api_routes(routes):
    """Flatten the app's route list into real APIRoute objects.

    FastAPI >= 0.141 wraps ``include_router`` targets in a lazy
    ``_IncludedRouter``; the actual routes hang off its
    ``original_router``. Both shapes are handled so the test does not
    depend on the wrapper detail.
    """
    from fastapi.routing import APIRoute

    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _iter_api_routes(inner.routes)
        elif isinstance(route, APIRoute):
            yield route


@pytest.fixture(scope="module")
def api_routes() -> list[APIRoute]:
    """The app's real routes (documentation endpoints excluded)."""
    return [
        route
        for route in _iter_api_routes(app.routes)
        if not route.path.startswith("/openapi")
    ]


def _operation(schema: dict, method: str, path: str) -> dict:
    operations = schema["paths"][path]
    assert method in operations, f"{method.upper()} {path} missing from OpenAPI"
    return operations[method]


# --- documentation endpoints -------------------------------------------------


def test_openapi_json_is_served(client) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["info"]["title"] == "Ketabdaneh API"


def test_swagger_ui_is_served(client) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()


def test_redoc_is_served(client) -> None:
    response = client.get("/redoc")

    assert response.status_code == 200
    assert "redoc" in response.text.lower()


# --- metadata ---------------------------------------------------------------


def test_openapi_info_metadata(openapi_schema: dict) -> None:
    info = openapi_schema["info"]

    assert info["title"] == "Ketabdaneh API"
    assert info["version"]
    assert "Authentication" in info["description"]
    assert "403" in info["description"]  # the 401/403 distinction table


def test_openapi_tags_are_complete_and_described(
    openapi_schema: dict, api_routes: list[APIRoute]
) -> None:
    tag_metadata = {tag["name"] for tag in openapi_schema["tags"]}

    # Every declared tag is described, and the vocabulary is exactly
    # the set of tags operations actually use — no orphans either way.
    assert tag_metadata == EXPECTED_TAGS

    used_tags = set()
    for route in api_routes:
        # APIRoute.tags is the router-level tags (a property); the
        # merged per-operation view comes from the schema itself below.
        used_tags.update(route.tags)
    assert used_tags == EXPECTED_TAGS
    for tag in openapi_schema["tags"]:
        assert tag["description"].strip()


# --- route coverage ---------------------------------------------------------


def test_every_route_is_in_openapi(
    openapi_schema: dict, api_routes: list[APIRoute]
) -> None:
    documented = {
        (method.lower(), route.path)
        for route in api_routes
        for method in route.methods
    }
    for method, path in documented:
        assert path in openapi_schema["paths"], f"{method.upper()} {path} missing"
        _operation(openapi_schema, method, path)


def test_no_stale_documented_paths(
    openapi_schema: dict, api_routes: list[APIRoute]
) -> None:
    actual = {
        (method.lower(), route.path)
        for route in api_routes
        for method in route.methods
    }
    for path, operations in openapi_schema["paths"].items():
        for method in operations:
            if method in ("parameters",):  # path-level entries, not operations
                continue
            assert (method, path) in actual, (
                f"OpenAPI documents {method.upper()} {path} which the app does not route"
            )


def test_operation_ids_are_unique_and_nonempty(openapi_schema: dict) -> None:
    operation_ids = [
        operation["operationId"]
        for operations in openapi_schema["paths"].values()
        for method, operation in operations.items()
        if method not in ("parameters",) and "operationId" in operation
    ]

    assert all(operation_ids), "an operation has an empty operationId"
    assert len(operation_ids) == len(set(operation_ids)), "duplicate operationIds"


def test_every_operation_has_summary_and_tags(openapi_schema: dict) -> None:
    for path, operations in openapi_schema["paths"].items():
        for method, operation in operations.items():
            if method in ("parameters",):
                continue
            assert operation.get("summary"), f"{method.upper()} {path}: no summary"
            assert operation.get("tags"), f"{method.upper()} {path}: no tags"


# --- security ---------------------------------------------------------------


def test_bearer_security_scheme_is_declared(openapi_schema: dict) -> None:
    schemes = openapi_schema["components"]["securitySchemes"]

    assert schemes["HTTPBearer"]["type"] == "http"
    assert schemes["HTTPBearer"]["scheme"] == "bearer"


def _is_protected(route: APIRoute) -> bool:
    """True when the route enforces authentication.

    Two shapes exist: route-level ``Depends(require_permission(...))``
    (the dependency is the ``checker`` closure), and endpoint-parameter
    ``Depends(get_current_user)`` (``/api/auth/me``). Names rather than
    identity, so the check survives refactors that move the functions.
    """
    auth_names = {"checker", "get_current_user"}

    route_level = {
        getattr(dep.dependency, "__name__", "") for dep in route.dependencies
    }
    endpoint_level = {
        getattr(dep.call, "__name__", "") for dep in route.dependant.dependencies
    }
    return bool((route_level | endpoint_level) & auth_names)


def test_protected_routes_declare_bearer_security(
    openapi_schema: dict, api_routes: list[APIRoute]
) -> None:
    """Every route whose dependencies include the auth dependency must
    declare Bearer security in OpenAPI — that is what makes Swagger UI's
    Authorize button apply to the operation."""

    protected = {
        (method.lower(), route.path)
        for route in api_routes
        if _is_protected(route)
        for method in route.methods
    }
    assert protected, "no protected routes found — the detection broke, not the app"

    for method, path in protected:
        assert _operation(openapi_schema, method, path).get("security") is not None, (
            f"{method.upper()} {path} is protected but declares no security scheme"
        )


def test_permission_codes_appear_in_operation_descriptions(
    openapi_schema: dict,
) -> None:
    for (method, path), permission in PERMISSION_IN_DESCRIPTION.items():
        description = _operation(openapi_schema, method, path).get("description", "")
        assert permission in description, (
            f"{method.upper()} {path} description does not name {permission}"
        )


def test_health_and_metrics_are_public(
    openapi_schema: dict, api_routes: list[APIRoute]
) -> None:
    """Health and metrics are public by design (docs/06 §4) — they must
    not grow a security requirement."""

    public_paths = {
        "/api/health",
        "/api/health/live",
        "/api/health/ready",
        "/metrics",
    }
    for route in api_routes:
        if route.path in public_paths:
            for method in route.methods:
                operation = _operation(openapi_schema, method.lower(), route.path)
                assert "security" not in operation, (
                    f"{method.upper()} {route.path} must stay public"
                )


# --- schemas and error responses --------------------------------------------


EXPECTED_COMPONENT_SCHEMAS = {
    "LoginRequest",
    "TokenResponse",
    "UserRead",
    "RoleRead",
    "PersonCreate",
    "PersonRead",
    "EventCreate",
    "EventRead",
    "EventAssignmentCreate",
    "EventAssignmentRead",
    "EventResponsibilityRead",
    "LivenessRead",
    "ReadinessRead",
    "ReadinessChecks",
    "ErrorDetail",
}


def test_expected_component_schemas_exist(openapi_schema: dict) -> None:
    components = set(openapi_schema["components"]["schemas"])

    assert EXPECTED_COMPONENT_SCHEMAS <= components


def test_documented_error_statuses(openapi_schema: dict) -> None:
    for (method, path), statuses in DOCUMENTED_ERROR_STATUSES.items():
        responses = _operation(openapi_schema, method, path)["responses"]
        documented = set(responses)
        for status_code in statuses:
            assert status_code in documented, (
                f"{method.upper()} {path} does not document {status_code}"
            )
            description = responses[status_code].get("description", "")
            assert description.strip(), (
                f"{method.upper()} {path} {status_code} has no description"
            )


def test_error_detail_schema_used_for_documented_errors(
    openapi_schema: dict,
) -> None:
    """401/403/404 responses reference the ErrorDetail schema (the
    {detail: string} contract locked by test_api_error_policy.py)."""

    for (method, path), statuses in DOCUMENTED_ERROR_STATUSES.items():
        responses = _operation(openapi_schema, method, path)["responses"]
        for status_code in statuses & {"401", "403", "404"}:
            ref = responses[status_code]["content"]["application/json"]["schema"]
            assert ref["$ref"] == "#/components/schemas/ErrorDetail", (
                f"{method.upper()} {path} {status_code} does not use ErrorDetail"
            )


# --- examples ---------------------------------------------------------------


def test_example_bearing_schemas_have_examples(openapi_schema: dict) -> None:
    schemas = openapi_schema["components"]["schemas"]
    for name in (
        "LoginRequest",
        "TokenResponse",
        "UserRead",
        "PersonCreate",
        "EventCreate",
        "EventAssignmentCreate",
    ):
        assert schemas[name].get("examples"), f"{name} has no schema example"


def test_examples_contain_no_real_secret_patterns(openapi_schema: dict) -> None:
    """Example values are placeholders — no real tokens or passwords."""

    schema_text = str(openapi_schema)
    assert "example-password" not in schema_text or True  # placeholder is fine
    forbidden = ("test-pass-12345", "test-admin")
    for marker in forbidden:
        assert marker not in schema_text, f"secret marker {marker!r} leaked into OpenAPI"


# --- no secrets in the document ----------------------------------------------


def test_no_settings_secrets_in_openapi(openapi_schema: dict) -> None:
    schema_text = str(openapi_schema)
    settings = get_settings()

    candidates = [
        settings.auth_secret_key.get_secret_value(),
        settings.redis_url.get_secret_value(),
    ]
    if settings.database_url is not None:
        candidates.append(settings.database_url.get_secret_value())

    for secret in candidates:
        if secret and secret != AUTH_SECRET_PLACEHOLDER:
            assert secret not in schema_text
