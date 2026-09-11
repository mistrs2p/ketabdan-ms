"""Container healthcheck for the notification worker (Task 5.11).

Docker needs a healthcheck command; the worker deliberately serves no
HTTP (docs/01 §10 — ``WORKER_METRICS_PORT`` is 0 by default), so this
uses the worker-health mechanism Task 5.9 already established: the
running arq worker refreshes ``<queue>:health`` in Redis every 30s with
a 31s TTL. Exit 0 = a live worker heartbeat exists; exit 1 = it does
not (no worker has refreshed the key within its TTL).

Deliberately NOT an API readiness substitute: this proves *a worker
process is alive*, the same honest signal ``/api/health/ready``'s
``worker`` check reports (app/api/health.py).

Runs inside the worker container (same image as the API — arq depends
on redis-py, so ``import redis`` needs no extra dependency). Reads
REDIS_URL from the environment like every other runtime setting; on any
connection error the check fails (exit non-zero), which is the correct
answer — no Redis, no heartbeat.
"""

import sys

import redis
from arq.constants import health_check_key_suffix

from app.worker.jobs import NOTIFICATION_QUEUE_NAME

# Composed exactly as arq's Worker does (queue_name + arq's suffix).
WORKER_HEALTH_KEY = NOTIFICATION_QUEUE_NAME + health_check_key_suffix


def main() -> int:
    from os import environ

    client = redis.Redis.from_url(
        environ["REDIS_URL"],
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    return 0 if client.exists(WORKER_HEALTH_KEY) else 1


if __name__ == "__main__":
    sys.exit(main())
