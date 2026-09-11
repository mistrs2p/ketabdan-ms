"""Tests for the Telegram and Bale notification providers (Task 5.6).

The full required matrix runs for BOTH providers via parametrization —
the two wire contracts were independently verified to match (docs/01
§6.1), so the matrix is shared, but each case asserts each provider's
own endpoint and channel.

No test touches the network: every request is served by an in-memory
``httpx2.MockTransport`` that records what the provider sent. The bot
token below is an obviously fake constant, never a real credential.
"""

import asyncio
import dataclasses
import json
from collections.abc import Awaitable, Callable

import httpx2
import pytest
from httpx2 import MockTransport, Request, Response

from app.notifications import (
    NotificationChannel,
    NotificationMessage,
    NotificationRecipient,
    NotificationResult,
    NotificationRejectedError,
    ProviderUnavailableError,
)
from app.notifications.bale import BaleNotificationProvider
from app.notifications.telegram import TelegramNotificationProvider

# Clearly fake, structurally plausible bot token — never a real one.
BOT_TOKEN = "1100000001:AA-test-fake-token-never-real-000"

PERSIAN_TEXT = "رویداد «تحلیل کتاب» جمعه ساعت ۱۷ برگزار می‌شود."
MIXED_TEXT = "Event 5PM Friday — جمعه ساعت ۱۷"

SUCCESS_BODY = {"ok": True, "result": {"message_id": 4242, "text": "…"}}


class ProviderCase:
    """One concrete provider under test, with its verified contract."""

    def __init__(
        self,
        provider_cls: type,
        name: str,
        channel: NotificationChannel,
        base_url: str,
    ) -> None:
        self.provider_cls = provider_cls
        self.name = name
        self.channel = channel
        self.base_url = base_url

    def endpoint(self, token: str = BOT_TOKEN) -> str:
        return f"{self.base_url}/bot{token}/sendMessage"

    def make_provider(
        self, *, bot_token: str | None = BOT_TOKEN, outcomes: tuple | list = ()
    ):
        """Build the provider wired to a recording mock transport.

        ``outcomes`` are served in order: a Response is returned, an
        Exception is raised (transport-level failure). Recorded requests
        land on ``provider_transport_requests``.
        """
        requests: list[Request] = []
        queue = list(outcomes)

        def handler(request: Request) -> Response:
            requests.append(request)
            if queue:
                outcome = queue.pop(0)
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
            return Response(200, json=SUCCESS_BODY)

        provider = self.provider_cls(
            bot_token=bot_token, transport=MockTransport(handler)
        )
        return provider, requests


CASES = [
    ProviderCase(
        TelegramNotificationProvider,
        "telegram",
        NotificationChannel.TELEGRAM,
        "https://api.telegram.org",
    ),
    ProviderCase(
        BaleNotificationProvider,
        "bale",
        NotificationChannel.BALE,
        "https://tapi.bale.ai",
    ),
]


@pytest.fixture(params=CASES, ids=[c.name for c in CASES])
def case(request: pytest.FixtureRequest) -> ProviderCase:
    return request.param


def run(coro: Callable[[], Awaitable[object]]) -> object:
    return asyncio.run(coro())


def make_message(
    case: ProviderCase, *, text: str = "Event created", address: str = "100200300"
) -> NotificationMessage:
    return NotificationMessage(
        recipient=NotificationRecipient(channel=case.channel, address=address),
        text=text,
        category="event",
    )


def sent_json(request: Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


# --- 1/2. successful send, external message id ----------------------------


def test_successful_send(case: ProviderCase) -> None:
    provider, _ = case.make_provider()

    result = run(lambda: provider.send(make_message(case)))

    assert result == NotificationResult(
        success=True,
        channel=case.channel,
        external_message_id="4242",
    )


def test_external_message_id_is_extracted_and_stringified(case: ProviderCase) -> None:
    provider, _ = case.make_provider(
        outcomes=[Response(200, json={"ok": True, "result": {"message_id": 9871}})]
    )

    result = run(lambda: provider.send(make_message(case)))

    assert result.success is True
    assert result.external_message_id == "9871"


# --- 3/4. endpoint construction and authentication --------------------------


def test_correct_endpoint_and_method(case: ProviderCase) -> None:
    provider, requests = case.make_provider()

    run(lambda: provider.send(make_message(case)))

    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert str(requests[0].url) == case.endpoint()


def test_authentication_is_the_bot_token_in_the_url_path(case: ProviderCase) -> None:
    # The verified contract authenticates via /bot<token>/ in the URL —
    # there is no Authorization header and no token in the JSON body.
    provider, requests = case.make_provider()

    run(lambda: provider.send(make_message(case)))

    assert str(requests[0].url) == case.endpoint()
    assert "authorization" not in {
        key.lower() for key in requests[0].headers.keys()
    }
    assert BOT_TOKEN not in sent_json(requests[0]).values()


# --- 5/6/7. recipient, message body, Unicode --------------------------------


def test_recipient_address_is_the_chat_id(case: ProviderCase) -> None:
    provider, requests = case.make_provider()

    run(lambda: provider.send(make_message(case, address="987654321")))

    assert sent_json(requests[0])["chat_id"] == "987654321"


def test_message_text_is_sent_verbatim(case: ProviderCase) -> None:
    provider, requests = case.make_provider()

    run(lambda: provider.send(make_message(case, text=MIXED_TEXT)))

    assert sent_json(requests[0])["text"] == MIXED_TEXT


@pytest.mark.parametrize("text", [PERSIAN_TEXT, MIXED_TEXT, "plain ascii"])
def test_unicode_is_preserved(case: ProviderCase, text: str) -> None:
    provider, requests = case.make_provider()

    run(lambda: provider.send(make_message(case, text=text)))

    # Round-trips through JSON unchanged — no ASCII mangling of Persian.
    assert sent_json(requests[0])["text"] == text


# --- 8-11. HTTP status mapping -----------------------------------------------


def test_400_is_a_rejection(case: ProviderCase) -> None:
    provider, _ = case.make_provider(
        outcomes=[
            Response(
                400,
                json={
                    "ok": False,
                    "error_code": 400,
                    "description": "Bad Request: chat not found",
                },
            )
        ]
    )

    with pytest.raises(NotificationRejectedError) as excinfo:
        run(lambda: provider.send(make_message(case)))

    assert "chat not found" in str(excinfo.value)


def test_403_is_a_rejection(case: ProviderCase) -> None:
    # e.g. Telegram's "Forbidden: bot was blocked by the user" — the
    # recipient refused the bot, so this notification is rejected.
    provider, _ = case.make_provider(
        outcomes=[
            Response(
                403,
                json={"ok": False, "error_code": 403, "description": "Forbidden"},
            )
        ]
    )

    with pytest.raises(NotificationRejectedError):
        run(lambda: provider.send(make_message(case)))


def test_401_is_a_configuration_failure(case: ProviderCase) -> None:
    provider, _ = case.make_provider(
        outcomes=[
            Response(
                401,
                json={"ok": False, "error_code": 401, "description": "Unauthorized"},
            )
        ]
    )

    with pytest.raises(ProviderUnavailableError, match="bot token"):
        run(lambda: provider.send(make_message(case)))


def test_429_is_rate_limiting(case: ProviderCase) -> None:
    provider, _ = case.make_provider(
        outcomes=[
            Response(
                429,
                json={
                    "ok": False,
                    "error_code": 429,
                    "description": "Too Many Requests",
                    "parameters": {"retry_after": 33},
                },
            )
        ]
    )

    with pytest.raises(ProviderUnavailableError, match="rate limit") as excinfo:
        run(lambda: provider.send(make_message(case)))

    assert "33" in str(excinfo.value)  # provider's retry hint is preserved


def test_5xx_is_provider_unavailable(case: ProviderCase) -> None:
    provider, _ = case.make_provider(
        outcomes=[Response(503, json={"ok": False, "error_code": 503})]
    )

    with pytest.raises(ProviderUnavailableError, match="HTTP 503"):
        run(lambda: provider.send(make_message(case)))


# --- 12/13. transport failures ------------------------------------------------


def test_timeout_is_provider_unavailable(case: ProviderCase) -> None:
    provider, _ = case.make_provider(outcomes=[httpx2.ReadTimeout("read timed out")])

    with pytest.raises(ProviderUnavailableError, match="timed out"):
        run(lambda: provider.send(make_message(case)))


def test_connection_failure_is_provider_unavailable(case: ProviderCase) -> None:
    provider, _ = case.make_provider(
        outcomes=[httpx2.ConnectError("connection refused")]
    )

    with pytest.raises(ProviderUnavailableError, match="could not be reached"):
        run(lambda: provider.send(make_message(case)))


# --- 14. malformed / unexpected responses --------------------------------------


@pytest.mark.parametrize(
    "response",
    [
        Response(200, text="<html>gateway error INTERNAL-MARKER-42</html>"),
        Response(200, json={"ok": False, "error_code": 400}),
        Response(200, json={"ok": True, "result": {"no_message_id": True}}),
        Response(200, json={"unexpected": "shape"}),
        Response(302, text="moved"),  # redirects are never followed
    ],
    ids=["html-body", "ok-false", "missing-message-id", "wrong-shape", "redirect"],
)
def test_unexpected_response_is_provider_unavailable(
    case: ProviderCase, response: Response
) -> None:
    provider, _ = case.make_provider(outcomes=[response])

    with pytest.raises(ProviderUnavailableError, match="unexpected response"):
        run(lambda: provider.send(make_message(case)))


# --- 15. missing bot token ------------------------------------------------------


def test_missing_bot_token_fails_at_send_time(case: ProviderCase) -> None:
    provider, _ = case.make_provider(bot_token=None)

    with pytest.raises(ProviderUnavailableError, match="not configured"):
        run(lambda: provider.send(make_message(case)))


def test_empty_bot_token_is_treated_as_missing(case: ProviderCase) -> None:
    provider, _ = case.make_provider(bot_token="")

    with pytest.raises(ProviderUnavailableError, match="not configured"):
        run(lambda: provider.send(make_message(case)))


# --- 16/17/18. no token or raw-response leakage ---------------------------------


@pytest.mark.parametrize(
    "outcome",
    [
        Response(400, json={"ok": False, "error_code": 400, "description": "no"}),
        Response(401, json={"ok": False, "error_code": 401}),
        Response(429, json={"ok": False, "error_code": 429}),
        Response(500, json={"ok": False, "error_code": 500}),
        Response(200, text="<html>RAW-RESPONSE-MARKER</html>"),
        httpx2.ReadTimeout("read timed out"),
        httpx2.ConnectError("connection refused"),
    ],
    ids=["400", "401", "429", "500", "malformed", "timeout", "connection"],
)
def test_bot_token_never_appears_in_exceptions(
    case: ProviderCase, outcome: object
) -> None:
    provider, _ = case.make_provider(outcomes=[outcome])

    with pytest.raises((NotificationRejectedError, ProviderUnavailableError)) as excinfo:
        run(lambda: provider.send(make_message(case)))

    assert BOT_TOKEN not in str(excinfo.value)
    assert case.base_url not in str(excinfo.value)


def test_bot_token_never_appears_in_the_result(case: ProviderCase) -> None:
    provider, _ = case.make_provider()

    result = run(lambda: provider.send(make_message(case)))

    assert BOT_TOKEN not in str(result)
    assert {f.name for f in dataclasses.fields(result)} == {
        "success",
        "channel",
        "external_message_id",
        "error_code",
        "error_message",
    }


def test_raw_response_body_is_not_leaked_in_errors(case: ProviderCase) -> None:
    provider, _ = case.make_provider(
        outcomes=[Response(502, text="<html>RAW-RESPONSE-MARKER 7f3a</html>")]
    )

    with pytest.raises(ProviderUnavailableError) as excinfo:
        run(lambda: provider.send(make_message(case)))

    assert "RAW-RESPONSE-MARKER" not in str(excinfo.value)


# --- message size policy (docs/01 §6.4) -----------------------------------------


def test_oversized_message_is_rejected_not_truncated(case: ProviderCase) -> None:
    provider, requests = case.make_provider()
    long_text = "x" * 4097

    with pytest.raises(NotificationRejectedError) as excinfo:
        run(lambda: provider.send(make_message(case, text=long_text)))

    assert excinfo.value.error_code == "message_too_long"
    assert requests == []  # nothing was sent — and nothing was altered


def test_max_length_message_is_sent(case: ProviderCase) -> None:
    provider, requests = case.make_provider()

    result = run(lambda: provider.send(make_message(case, text="x" * 4096)))

    assert result.success is True
    assert len(sent_json(requests[0])["text"]) == 4096


# --- SSRF safety (docs/01 §6): recipient data can never steer the URL ----------


def test_recipient_address_is_data_not_a_url(case: ProviderCase) -> None:
    provider, requests = case.make_provider()

    run(
        lambda: provider.send(
            make_message(case, address="https://internal-service:8000/admin")
        )
    )

    # The HTTP destination is always the provider's constant endpoint;
    # the recipient string only ever travels inside the JSON body.
    assert str(requests[0].url) == case.endpoint()
    assert sent_json(requests[0])["chat_id"] == "https://internal-service:8000/admin"
