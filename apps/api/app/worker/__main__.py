"""Run the notification background worker from the CLI:

    python -m app.worker

Equivalent to ``arq app.worker.worker.WorkerSettings``. Reads the same
environment/.env configuration as the API (REDIS_URL, provider tokens,
retry policy) — no separate configuration surface.
"""

from arq import run_worker

from app.worker.worker import WorkerSettings

if __name__ == "__main__":
    run_worker(WorkerSettings)
