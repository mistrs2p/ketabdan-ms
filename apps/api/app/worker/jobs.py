"""The queued notification job contract (Task 5.7).

A ``NotificationJob`` is the *serializable* image of a
``NotificationMessage``: exactly what crosses the process boundary between
the enqueueing application and the background worker. It carries only
stable, JSON-serializable data — the generic notification model semantics
(channel, recipient address, text, category, metadata) and **nothing
provider-specific** and no Python objects, provider instances, callbacks,
credentials, or Redis endpoints.

Reconstruction on the worker side goes through the same Task 5.5 model
(``NotificationRecipient`` / ``NotificationMessage``) and the same
``NotificationDispatcher`` — the worker never duplicates provider logic.
"""

import dataclasses
from typing import Any

from app.notifications import (
    InvalidNotificationError,
    NotificationChannel,
    NotificationMessage,
    NotificationRecipient,
)

# The Redis sorted-set that holds pending jobs. One constant so the
# enqueueing side and the worker can never drift apart.
NOTIFICATION_QUEUE_NAME = "ketabdaneh:notifications"

# The arq function name the job is enqueued under (jobs are looked up by
# name on the worker side).
DELIVER_FUNCTION_NAME = "deliver_notification"

# Exactly the keys a serialized job payload may carry — nothing else.
_PAYLOAD_KEYS = frozenset({"channel", "address", "text", "category", "metadata"})


@dataclasses.dataclass(frozen=True)
class NotificationJob:
    """The queue-safe form of one notification to deliver in the background."""

    channel: str
    address: str
    text: str
    category: str
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("channel", "address", "text", "category"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise InvalidNotificationError(
                    f"Notification job field {field_name!r} must be a "
                    "non-empty string."
                )
        if not isinstance(self.metadata, dict):
            raise InvalidNotificationError(
                "Notification job metadata must be a mapping."
            )
        # Copy so a caller mutating its dict afterwards cannot change an
        # already-constructed (frozen) job.
        object.__setattr__(self, "metadata", dict(self.metadata))

    @classmethod
    def from_message(cls, message: NotificationMessage) -> "NotificationJob":
        """Flatten a generic NotificationMessage into its queue-safe form."""
        return cls(
            channel=str(message.recipient.channel),
            address=message.recipient.address,
            text=message.text,
            category=message.category,
            metadata=dict(message.metadata),
        )

    def to_message(self) -> NotificationMessage:
        """Reconstruct the generic NotificationMessage (Task 5.5 model)."""
        return NotificationMessage(
            recipient=NotificationRecipient(
                channel=NotificationChannel(self.channel),  # type: ignore[arg-type]
                address=self.address,
            ),
            text=self.text,
            category=self.category,
            metadata=self.metadata,
        )

    def to_payload(self) -> dict[str, Any]:
        """The JSON-serializable dict stored in the queue."""
        return {
            "channel": self.channel,
            "address": self.address,
            "text": self.text,
            "category": self.category,
            "metadata": self.metadata,
        }

    @classmethod
    def from_payload(cls, payload: object) -> "NotificationJob":
        """Rebuild a job from queue data, strictly.

        Only the known key set is accepted (unknown keys are a corrupt or
        hostile payload and are rejected, not ignored). Raises
        ``InvalidNotificationError`` on any malformed input.
        """
        if not isinstance(payload, dict):
            raise InvalidNotificationError(
                "Notification job payload must be a mapping."
            )
        keys = set(payload.keys())
        mandatory = _PAYLOAD_KEYS - {"metadata"}
        unknown = keys - _PAYLOAD_KEYS
        missing = mandatory - keys
        if unknown or missing:
            raise InvalidNotificationError(
                "Notification job payload keys are wrong "
                f"(unknown: {sorted(unknown)}, missing: {sorted(missing)}); "
                f"expected {sorted(_PAYLOAD_KEYS)}."
            )
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            raise InvalidNotificationError(
                "Notification job metadata must be a mapping."
            )
        return cls(
            channel=payload["channel"],  # type: ignore[arg-type]
            address=payload["address"],  # type: ignore[arg-type]
            text=payload["text"],  # type: ignore[arg-type]
            category=payload["category"],  # type: ignore[arg-type]
            metadata=metadata,  # type: ignore[arg-type]
        )
