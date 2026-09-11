"""Bale notification provider (Task 5.6).

The only place in the codebase that knows Bale specifics. Independently
verified against Bale's current bot API (2026-09, via the ``balethon``
client implementing it): POST ``https://tapi.bale.ai/bot<token>/
sendMessage`` with the same JSON parameters (``chat_id``, ``text``) and
the same response envelope as the Telegram Bot API — ``{"ok": ...,
"result": {...}}`` on success, HTTP-style ``error_code`` semantics on
failure (400 bad request, 401 unauthorized, 403 forbidden, 429 too many
requests, 5xx internal). The shared wire handling lives in
``_botapi.py``; only this module owns Bale's endpoint and limits.

No public text-length limit could be verified for Bale; the Telegram-
compatible 4096-character guard is applied as a conservative bound
(oversized messages are rejected, never truncated — docs/01 §6.4).
"""

import httpx2

from app.notifications._botapi import (
    DEFAULT_TIMEOUT_SECONDS,
    send_bot_api_message,
)
from app.notifications.models import (
    NotificationChannel,
    NotificationMessage,
    NotificationResult,
)

BASE_URL = "https://tapi.bale.ai"

# Conservative guard (no documented Bale limit verified — see module
# docstring); oversized messages are rejected, never truncated.
MAX_TEXT_LENGTH = 4096


class BaleNotificationProvider:
    """Delivers notifications on ``NotificationChannel.BALE``.

    Constructed with the bot token from configuration (never a caller-
    supplied value); ``transport`` is a test seam for injecting a mocked
    HTTP transport — production leaves it ``None``.
    """

    channel = NotificationChannel.BALE

    def __init__(
        self,
        *,
        bot_token: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def send(
        self, message: NotificationMessage
    ) -> NotificationResult:
        return await send_bot_api_message(
            transport=self._transport,
            base_url=BASE_URL,
            bot_token=self._bot_token,
            channel=self.channel,
            provider_name="Bale",
            message=message,
            max_text_length=MAX_TEXT_LENGTH,
            timeout_seconds=self._timeout_seconds,
        )
