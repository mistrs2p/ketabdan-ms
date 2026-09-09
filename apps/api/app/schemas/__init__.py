"""API schemas for the Ketabdaneh backend.

Schemas are the HTTP/JSON contract (docs/01 §4): pydantic models that shape
what the API accepts and returns. They deliberately mirror the domain models
without leaking them — a schema says what crosses the boundary, not how the
data is stored.
"""
