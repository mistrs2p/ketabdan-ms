"""Background notification delivery infrastructure (Task 5.7).

Two halves, one queue contract (``jobs.py``):

    application / business service
          ↓  enqueue_notification(...)            service.py
    Redis (arq queue, JSON-serialized jobs)
          ↓  Worker                               worker.py
    NotificationDispatcher (Task 5.5 factory)     factory boundary
          ↓
    Telegram / Bale provider → external delivery

The API application does not need Redis to import or serve; the
connection happens when this infrastructure is actually used (enqueue) or
started (worker). Delivery is at-least-once (see docs/01 §6.5).
"""

from app.worker.errors import (
    NotificationQueueError,
    PermanentNotificationFailure,
    WorkerError,
)
from app.worker.jobs import (
    DELIVER_FUNCTION_NAME,
    NOTIFICATION_QUEUE_NAME,
    NotificationJob,
)
from app.worker.retry import RetryPolicy
from app.worker.service import BackgroundNotificationService

__all__ = [
    "DELIVER_FUNCTION_NAME",
    "BackgroundNotificationService",
    "NOTIFICATION_QUEUE_NAME",
    "NotificationJob",
    "NotificationQueueError",
    "PermanentNotificationFailure",
    "RetryPolicy",
    "WorkerError",
]
