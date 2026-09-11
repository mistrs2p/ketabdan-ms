"""Run the notification background worker from the CLI:

    python -m app.worker

Equivalent to ``arq app.worker.worker.WorkerSettings``. Reads the same
environment/.env configuration as the API (REDIS_URL, provider tokens,
retry policy) — no separate configuration surface.

Task 5.8: configures application logging before the worker starts. Only
the ``arq`` CLI applies its own log config — ``run_worker`` does not — so
without this the worker process would fall back to stdlib defaults (no
handler, "no handlers could be found" behavior on old Pythons; lastResort
stderr with no format on 3.12).
"""

from arq import run_worker

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.worker.worker import WorkerSettings

if __name__ == "__main__":
    configure_logging(level=get_settings().log_level)
    run_worker(WorkerSettings)
