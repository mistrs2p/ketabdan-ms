"""The notification provider interface — the boundary of the abstraction.

Business/domain code depends only on the dispatcher and the neutral models
in ``models.py``; everything provider-specific (payload formats, URLs,
SDKs, credentials) stays behind a ``NotificationProvider`` implementation.
``send`` is async because real providers (Task 5.6: Telegram/Bale) will
perform network I/O; local/in-app future providers can simply not await
anything. The protocol is not bound to HTTP on purpose.
"""

from typing import Protocol

from app.notifications.models import NotificationChannel, NotificationMessage, NotificationResult


class NotificationProvider(Protocol):
    """Anything that can deliver a notification on exactly one channel.

    Implementations (Task 5.6 and beyond) own the translation from the
    neutral ``NotificationMessage`` to their platform's payload. They
    report failures by raising the domain errors from
    ``app.notifications.errors`` (or returning a failure
    ``NotificationResult``); unexpected exceptions are normalized by the
    dispatcher.
    """

    @property
    def channel(self) -> NotificationChannel:
        """The channel this provider delivers on; one provider, one channel."""
        ...

    async def send(self, message: NotificationMessage) -> NotificationResult:
        """Deliver one notification and return the normalized result."""
        ...
