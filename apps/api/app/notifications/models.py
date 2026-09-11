"""Provider-neutral notification domain model.

Plain frozen dataclasses, deliberately independent of the HTTP schemas in
``app/schemas/`` (these are internal contracts, never request/response
bodies) and of any persistence model — Task 5.5 is the abstraction layer
only; delivery history/queues arrive with Task 5.7 if a requirement asks
for them.

The model is provider-agnostic on purpose: a recipient is a *channel* plus
a provider-external *address*. Nothing here knows about Telegram chat ids,
Bale ids, phone numbers, or any provider payload format — translating an
address into a provider call is the provider's job (app/notifications/
providers.py).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from app.notifications.errors import InvalidNotificationError


class NotificationChannel(StrEnum):
    """Stable delivery-channel identifiers.

    Telegram and Bale are defined now because they are the known future
    integrations (docs/00 §6) — but no provider for them exists yet
    (Task 5.6). Adding a channel later (email, SMS, in-app) means adding
    a member here plus a provider; nothing else in the contract changes.
    """

    TELEGRAM = "telegram"
    BALE = "bale"


@dataclass(frozen=True)
class NotificationRecipient:
    """Where a notification goes: a channel plus that channel's external
    address (a provider-specific identifier, opaque to business code)."""

    channel: NotificationChannel
    address: str

    def __post_init__(self) -> None:
        if not self.address.strip():
            raise InvalidNotificationError(
                "Notification recipient address must not be empty."
            )


@dataclass(frozen=True)
class NotificationMessage:
    """A single notification to one recipient on one channel.

    Multi-channel delivery (e.g. the same text via Telegram *and* Bale) is
    expressed as several messages, one per recipient — see
    ``NotificationDispatcher.send_many``.
    """

    recipient: NotificationRecipient
    text: str
    category: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise InvalidNotificationError("Notification text must not be empty.")
        if not self.category.strip():
            raise InvalidNotificationError("Notification category must not be empty.")
        # Copy so a caller mutating its dict afterwards cannot change an
        # already-constructed (frozen) message.
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def channel(self) -> NotificationChannel:
        """Shortcut — the recipient's channel is the message's channel."""
        return self.recipient.channel


@dataclass(frozen=True)
class NotificationResult:
    """Normalized outcome of one delivery attempt.

    The only shape business code ever sees — providers return it, and the
    dispatcher maps provider failures onto it. Provider-internal details
    (raw API responses, payloads) never appear here; ``error_message`` is
    diagnostic text for logs/operators, not for display to end users.
    """

    success: bool
    channel: NotificationChannel
    external_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
