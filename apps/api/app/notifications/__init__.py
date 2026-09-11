"""Notification abstraction — the provider-agnostic boundary (Phase 5.5).

Business services depend only on this package's neutral contract:

    business service
          ↓
    NotificationDispatcher.send / send_many      (dispatcher.py)
          ↓
    NotificationProvider protocol                (providers.py)
          ↓
    concrete providers — Telegram / Bale / …     (Task 5.6, not yet built)

Status (Task 5.5): the internal contract and dispatch infrastructure only.
There are **no real providers** — no Telegram, no Bale, no SDKs, no
network calls, no credentials, no persistence. The first concrete
providers arrive with Task 5.6; retries/background delivery with Task 5.7.
"""

from app.notifications.dispatcher import NotificationDispatcher
from app.notifications.errors import (
    InvalidNotificationError,
    NotificationError,
    NotificationRejectedError,
    ProviderUnavailableError,
    UnsupportedChannelError,
)
from app.notifications.models import (
    NotificationChannel,
    NotificationMessage,
    NotificationRecipient,
    NotificationResult,
)
from app.notifications.providers import NotificationProvider

__all__ = [
    "InvalidNotificationError",
    "NotificationChannel",
    "NotificationDispatcher",
    "NotificationError",
    "NotificationMessage",
    "NotificationProvider",
    "NotificationRecipient",
    "NotificationRejectedError",
    "NotificationResult",
    "ProviderUnavailableError",
    "UnsupportedChannelError",
]
