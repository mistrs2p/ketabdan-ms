"""Notification-layer exceptions.

Distinct failure modes (docs/01 §6) so business code can decide whether a
notification failure is fatal, retryable, or ignorable — the notification
layer never converts them into a generic application error by itself.

Retries are explicitly out of scope here (Task 5.7 will own them).
"""


class NotificationError(Exception):
    """Base class for all notification-layer errors."""


class InvalidNotificationError(NotificationError, ValueError):
    """The notification or its recipient is malformed (empty text, empty
    recipient address, …). Raised at construction time, before any provider
    is involved."""


class UnsupportedChannelError(NotificationError):
    """No provider is registered for the notification's channel.

    A wiring/configuration problem (the dispatcher was built without a
    provider for that channel), not a delivery failure — so it is raised,
    not folded into a failure result.
    """

    def __init__(self, channel: str) -> None:
        super().__init__(f"No notification provider registered for channel: {channel}")
        self.channel = channel


class ProviderUnavailableError(NotificationError):
    """The provider exists but cannot deliver right now (network down,
    provider outage). Delivery failure — normalized into a
    ``provider_unavailable`` result by the dispatcher."""

    ERROR_CODE = "provider_unavailable"


class NotificationRejectedError(NotificationError):
    """The provider refused the notification (e.g. an address that is
    invalid *for that provider*). Delivery failure — normalized into a
    failure result carrying the provider's stable error code."""

    DEFAULT_ERROR_CODE = "notification_rejected"

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code or self.DEFAULT_ERROR_CODE
