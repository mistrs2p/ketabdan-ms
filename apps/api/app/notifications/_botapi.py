"""Shared wire handling for the Telegram-style Bot API providers.

Both verified provider contracts use the same wire shape:

- endpoint: ``POST {base_url}/bot{token}/sendMessage`` (token in the URL
  path — that is the providers' documented authentication mechanism)
- request: JSON body ``{"chat_id": <address>, "text": <text>}``
- response: JSON envelope ``{"ok": bool, "result": {...}, "error_code":
  int, "description": str, "parameters": {"retry_after": int}}`` with the
  HTTP status mirroring the envelope's ``error_code``.

Sources verified at implementation time (2026-09): Telegram via the
grammY type definitions generated from the official Bot API reference
(``sendMessage``: ``chat_id`` + ``text``, 1–4096 characters; envelope
``ok``/``result``/``error_code``/``description``/``parameters.retry_after``)
and via aiogram's client source (``https://api.telegram.org`` base URL);
Bale via the current ``balethon`` client source
(``https://tapi.bale.ai/bot<token>/<method>``, same JSON parameters, same
envelope, HTTP-style 400/401/403/429/5xx error semantics).

The helper keeps that common wire logic in ONE place; each provider
module (``telegram.py`` / ``bale.py``) owns its endpoint, channel, and
limits. If a provider's API ever diverges, that provider can stop using
this helper without the other being affected.

Security invariants (docs/01 §6):

- the request URL is assembled ONLY from the provider's constant base URL
  and the configured bot token — never from notification data, so a
  recipient address can never steer the HTTP destination (SSRF);
- raised messages never contain the bot token, the full URL, or raw
  response bodies — fixed diagnostic text plus the provider's short
  ``description`` field only;
- redirects are not followed.
"""

import httpx2

from app.notifications.errors import (
    NotificationRejectedError,
    ProviderUnavailableError,
)
from app.notifications.models import (
    NotificationChannel,
    NotificationMessage,
    NotificationResult,
)

# Bounded network time for one provider request. Providers should not
# hang the calling request indefinitely; retries are Task 5.7's concern.
DEFAULT_TIMEOUT_SECONDS = 10.0

# A 2xx response whose body is not the expected envelope (proxy error
# page, truncated body, …) is a provider-side anomaly, not a rejection.
UNEXPECTED_RESPONSE = "returned an unexpected response"


def _envelope_description(body: object) -> str | None:
    """The provider's short error text, when present and a string."""
    if isinstance(body, dict):
        description = body.get("description")
        if isinstance(description, str) and description:
            return description
    return None


def _retry_after(body: object) -> int | None:
    """The provider's suggested wait (seconds) on a 429, when present."""
    if isinstance(body, dict):
        parameters = body.get("parameters")
        if isinstance(parameters, dict):
            retry_after = parameters.get("retry_after")
            if isinstance(retry_after, int):
                return retry_after
    return None


async def send_bot_api_message(
    *,
    transport: httpx2.AsyncBaseTransport | None,
    base_url: str,
    bot_token: str | None,
    channel: NotificationChannel,
    provider_name: str,
    message: NotificationMessage,
    max_text_length: int,
    timeout_seconds: float,
) -> NotificationResult:
    """Deliver ``message`` via one Telegram-style Bot API and normalize
    the outcome into the generic contract.

    Raises the domain errors from ``app.notifications.errors`` for
    classified failures; the Task 5.5 dispatcher normalizes them into
    ``NotificationResult`` failures. Never raises with the token or the
    raw response body in the message.
    """
    if not bot_token:
        raise ProviderUnavailableError(
            f"{provider_name} provider is not configured: no bot token "
            "was provided (see TELEGRAM_BOT_TOKEN/BALE_BOT_TOKEN in "
            ".env.example)"
        )

    # Message-size policy (docs/01 §6.4): reject, never truncate or
    # chunk — silently altering user content is worse than failing.
    if len(message.text) > max_text_length:
        raise NotificationRejectedError(
            f"message text exceeds the {provider_name} limit of "
            f"{max_text_length} characters ({len(message.text)} given); "
            "chunking is not implemented",
            error_code="message_too_long",
        )

    # The recipient address is data (a chat id), carried in the JSON body
    # — it never becomes part of the URL.
    payload = {"chat_id": message.recipient.address, "text": message.text}
    url = f"{base_url}/bot{bot_token}/sendMessage"

    try:
        # One bounded request per send; follow_redirects=False so a
        # compromised/misbehaving provider cannot redirect us elsewhere.
        async with httpx2.AsyncClient(
            timeout=timeout_seconds,
            transport=transport,
            follow_redirects=False,
        ) as client:
            response = await client.post(url, json=payload)
    except httpx2.TimeoutException:
        # Fixed message: transport exception text may embed the request
        # URL (which contains the bot token).
        raise ProviderUnavailableError(
            f"{provider_name} request timed out after {timeout_seconds}s"
        ) from None
    except httpx2.RequestError:
        raise ProviderUnavailableError(
            f"{provider_name} could not be reached"
        ) from None

    try:
        body: object = response.json()
    except ValueError:
        body = None

    status = response.status_code
    if status == 429:
        wait = _retry_after(body)
        suffix = f" (retry after {wait}s)" if wait is not None else ""
        raise ProviderUnavailableError(
            f"{provider_name} rate limit exceeded{suffix}"
        )
    if status >= 500:
        raise ProviderUnavailableError(
            f"{provider_name} server error (HTTP {status})"
        )
    if status == 401:
        # The bot token was rejected — a configuration failure, not a
        # problem with this notification.
        raise ProviderUnavailableError(
            f"{provider_name} rejected the bot token (HTTP 401)"
        )
    if status >= 400:
        # 400/403/404…: the provider refused this recipient or message
        # (e.g. "chat not found", "bot was blocked by the user").
        description = _envelope_description(body)
        detail = f": {description}" if description else f" (HTTP {status})"
        raise NotificationRejectedError(
            f"{provider_name} rejected the notification{detail}"
        )

    # Success path: a 2xx whose envelope must carry the sent message id.
    if not isinstance(body, dict) or body.get("ok") is not True:
        raise ProviderUnavailableError(f"{provider_name} {UNEXPECTED_RESPONSE}")
    result = body.get("result")
    message_id = result.get("message_id") if isinstance(result, dict) else None
    if message_id is None:
        raise ProviderUnavailableError(f"{provider_name} {UNEXPECTED_RESPONSE}")

    return NotificationResult(
        success=True,
        channel=channel,
        external_message_id=str(message_id),
    )
