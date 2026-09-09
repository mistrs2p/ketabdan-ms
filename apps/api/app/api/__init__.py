"""HTTP routers for the Ketabdaneh backend.

One module per resource; every route lives under the ``/api`` prefix
(matching ``/api/health``). Routers own HTTP concerns only — parsing,
response shaping, status codes. Persistence goes through the ``get_db``
session dependency; anything beyond a trivial query belongs in a
service/module function, not in the route.
"""
