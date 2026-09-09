"""Service layer.

Domain logic that is more than a trivial query lives here, called by the
HTTP routers (docs/06 §3 rule 4). Services are HTTP-free: they raise
domain-meaningful exceptions, and the routers translate those into HTTP
responses. This keeps business logic out of route handlers and testable
without the HTTP stack.
"""
