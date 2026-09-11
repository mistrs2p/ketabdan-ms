"""Telegram notification provider (Task 5.6).

The only place in the codebase that knows Telegram specifics: the Bot API
endpoint, the sendMessage wire format, and Telegram's error semantics.
Business code talks to the Task 5.5 dispatcher and never sees any of it.

Verified contract (2026-09, docs/01 §6.1): POST
``https://api.telegram.org/bot<token>/sendMessage`` with JSON
``{"chat_id": ..., "text": ...}``; success returns
``{"ok": true, "result": {"message_id": ...}}``; failures return an
envelope whose ``error_code`` mirrors the HTTP status (401 bad token,
400/403 recipient/message rejected, 429 rate limited with
``parameters.retry_after``, 5xx provider error).
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

# Telegram's documented sendMessage text limit (1–4096 characters).
MAX_TEXT_LENGTH = 4096

BASE_URL = "https://api.telegram.org"


class TelegramNotificationProvider:
    """Delivers notifications on ``NotificationChannel.TELEGRAM``.

    Constructed with the bot token from configuration (never a caller-
    supplied value); ``transport`` is a test seam for injecting a mocked
    HTTP transport — production leaves it ``None``.
    """

    channel = NotificationChannel.TELEGRAM

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
            provider_name="Telegram",
            message=message,
            max_text_length=MAX_TEXT_LENGTH,
            timeout_seconds=self._timeout_seconds,
        )
