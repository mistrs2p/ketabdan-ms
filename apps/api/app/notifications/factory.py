"""Application-level notification wiring (Task 5.6).

The one place that reads configuration and constructs providers. Business
services receive a ready ``NotificationDispatcher`` and never know
environment variable names, endpoints, or provider classes.

Both providers are ALWAYS registered — an unconfigured one (missing
token) stays usable as a dispatcher target and reports a
provider-unavailable failure only when a send is actually attempted
(docs/01 §6.3). This keeps the application runnable with one, both, or
no providers configured.

Nothing consumes the dispatcher yet (no business-event triggers — a
future task); this factory is the extension point those triggers and the
Task 5.7 background delivery will build on.
"""

import httpx2
from pydantic import SecretStr

from app.core.config import Settings
from app.notifications.bale import BaleNotificationProvider
from app.notifications.dispatcher import NotificationDispatcher
from app.notifications.models import NotificationChannel
from app.notifications.providers import NotificationProvider
from app.notifications.telegram import TelegramNotificationProvider


def _token_or_none(token: SecretStr | None) -> str | None:
    """Unwrap a secret bot token for the provider; empty → unconfigured.

    The single point where the token leaves its SecretStr wrapper; the
    value is passed straight into the provider (never logged, never in
    error text). Empty string (an unset ".env" value) means "not
    configured" — exactly the pre-5.10 semantics.
    """
    if token is None:
        return None
    return token.get_secret_value() or None


def build_notification_dispatcher(
    settings: Settings,
    *,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> NotificationDispatcher:
    """Build the dispatcher with the providers the settings configure.

    ``transport`` is a test seam (mocked HTTP transport); production
    leaves it ``None`` so providers use real networking.
    """
    providers: dict[str, NotificationProvider] = {
        str(NotificationChannel.TELEGRAM): TelegramNotificationProvider(
            bot_token=_token_or_none(settings.telegram_bot_token),
            timeout_seconds=settings.notification_timeout_seconds,
            transport=transport,
        ),
        str(NotificationChannel.BALE): BaleNotificationProvider(
            bot_token=_token_or_none(settings.bale_bot_token),
            timeout_seconds=settings.notification_timeout_seconds,
            transport=transport,
        ),
    }
    return NotificationDispatcher(providers)
