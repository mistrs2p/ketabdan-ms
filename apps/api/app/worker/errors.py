"""Worker-layer exceptions (Task 5.7).

Two failure modes, kept distinct so callers (and operators) can tell them
apart — neither ever carries credentials, Redis URLs, or raw provider
responses in its message.
"""


class WorkerError(Exception):
    """Base class for background-delivery errors."""


class NotificationQueueError(WorkerError):
    """The job could not be enqueued (Redis unavailable / queue failure).

    Raised by the background notification service at *enqueue* time. The
    notification was NOT queued — the caller may surface this or fall back
    deliberately; nothing was delivered, and nothing will be delivered
    later.
    """


class PermanentNotificationFailure(WorkerError):
    """This notification will not be retried — it failed permanently.

    Raised inside the worker job for: provider-rejected notifications
    (invalid recipient, oversized message, …) and corrupt job payloads.
    The job ends as failed after its *first* attempt; the message carries
    the notification layer's stable error code and sanitized diagnostic
    text only.
    """
