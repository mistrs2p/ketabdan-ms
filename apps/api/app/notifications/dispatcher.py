"""The notification dispatcher — the only entry point business code uses.

Flow: a business service builds a neutral ``NotificationMessage`` and hands
it to ``NotificationDispatcher.send``; the dispatcher picks the provider
registered for the recipient's channel, the provider delivers it, and a
normalized ``NotificationResult`` comes back. Business code never
instantiates providers and never sees a provider-specific type.

Failure semantics (docs/01 §6):

- No provider registered for the channel → ``UnsupportedChannelError`` is
  *raised*: that is a wiring bug, not a delivery failure.
- Provider cannot deliver / rejects the notification / crashes → a
  *failure result* is returned (success=False with a stable error code).
  Nothing is silently swallowed: every failed attempt is visible in the
  returned result, and callers decide whether a failure is fatal,
  retryable, or ignorable. Retries themselves are Task 5.7.

The dispatcher holds no global state: it is constructed explicitly with
its providers (constructor injection, the same pattern as the service
layer) and can be built per-app or per-test.
"""

from collections.abc import Mapping, Sequence

from app.notifications.errors import (
    NotificationRejectedError,
    ProviderUnavailableError,
    UnsupportedChannelError,
)
from app.notifications.models import (
    NotificationChannel,
    NotificationMessage,
    NotificationResult,
)
from app.notifications.providers import NotificationProvider


class NotificationDispatcher:
    """Routes neutral notifications to the provider of their channel."""

    def __init__(
        self, providers: Mapping[str, NotificationProvider] | None = None
    ) -> None:
        # Keyed by the channel value ("telegram", "bale", …). A plain dict
        # built once at construction — no registry globals.
        self._providers: dict[str, NotificationProvider] = {}
        for provider in (providers or {}).values():
            self.register(provider)

    def register(self, provider: NotificationProvider) -> None:
        """Add a provider; one provider per channel (a second registration
        for the same channel is a wiring bug and raises)."""
        key = str(provider.channel)
        if key in self._providers:
            raise ValueError(
                f"A provider is already registered for channel: {key}"
            )
        self._providers[key] = provider

    def has_provider(self, channel: NotificationChannel | str) -> bool:
        """Whether a provider is registered for the channel."""
        return str(channel) in self._providers

    async def send(self, message: NotificationMessage) -> NotificationResult:
        """Deliver one notification via its recipient's channel."""
        channel = message.recipient.channel
        provider = self._providers.get(str(channel))
        if provider is None:
            raise UnsupportedChannelError(str(channel))
        return await self._deliver(provider, message)

    async def send_many(
        self, messages: Sequence[NotificationMessage]
    ) -> list[NotificationResult]:
        """Deliver several notifications (possibly across channels),
        independently — one result per message, in order."""
        return [await self.send(message) for message in messages]

    async def _deliver(
        self, provider: NotificationProvider, message: NotificationMessage
    ) -> NotificationResult:
        # Provider failures are normalized into results; they are not
        # raised, because a delivery failure is a *business* decision
        # (fatal / retryable / ignorable), not an application error.
        try:
            return await provider.send(message)
        except ProviderUnavailableError as exc:
            return NotificationResult(
                success=False,
                channel=message.channel,
                error_code=ProviderUnavailableError.ERROR_CODE,
                error_message=str(exc),
            )
        except NotificationRejectedError as exc:
            return NotificationResult(
                success=False,
                channel=message.channel,
                error_code=exc.error_code,
                error_message=str(exc),
            )
        except Exception as exc:
            # A provider crashing unexpectedly must not take down the
            # calling business flow, but it must not vanish either: it
            # comes back as a provider_error result. (Cancellation and
            # other BaseExceptions still propagate.)
            return NotificationResult(
                success=False,
                channel=message.channel,
                error_code="provider_error",
                error_message=f"{type(exc).__name__}: {exc}",
            )
