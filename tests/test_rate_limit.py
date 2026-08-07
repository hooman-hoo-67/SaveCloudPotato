"""
Waiting when a provider says to wait.

429 is not a failure. It is the provider saying "later", usually with a
number attached, and a client that treats it as an error fails a
transfer the provider was willing to complete a second later.

Reported from a real sync to Dropbox:

    HTTP 429 from https://content.dropboxapi.com/2/files/upload:
    {"error_summary": "too_many_write_operations/..",
     "error": {"reason": {".tag": "too_many_write_operations"},
               "retry_after": 1}}

Which is what uploading a save in parallel looks like from Dropbox's
side: several writes landing in one namespace at once.
"""

from __future__ import annotations

import email.message
import io
import urllib.error

import pytest

from savecloud.utils import http


class FakeResponse:
    """
    Enough of a urlopen result to be read once.
    """

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_) -> bool:
        return False


def _build(body: str, header=None, status: int = 429):
    """
    An HTTPError shaped the way urllib delivers one.
    """

    headers = email.message.Message()

    if header is not None:
        headers["Retry-After"] = str(header)

    return urllib.error.HTTPError(
        "https://content.dropboxapi.com/2/files/upload",
        status,
        "Too Many Requests",
        headers,
        io.BytesIO(body.encode("utf-8")),
    )


def rate_limited(retry_after=1, header=None):
    """
    The exact 429 Dropbox returned during a real sync.
    """

    reason = '{".tag": "too_many_write_operations"}'

    inner = f'"reason": {reason}'

    if retry_after is not None:
        inner += f', "retry_after": {retry_after}'

    body = (
        '{"error_summary": "too_many_write_operations/..", '
        f'"error": {{{inner}}}}}'
    )

    return _build(body, header)


@pytest.fixture
def slept(monkeypatch):
    """
    Record waits instead of taking them.
    """

    waits: list[float] = []

    monkeypatch.setattr(http.time, "sleep", waits.append)

    return waits


def responder(monkeypatch, *outcomes):
    """
    Make urlopen produce each outcome in turn.
    """

    remaining = list(outcomes)

    calls = {"count": 0}

    def urlopen(request, timeout=None):

        calls["count"] += 1

        outcome = remaining.pop(0) if remaining else FakeResponse(b"{}")

        if isinstance(outcome, Exception):
            raise outcome

        return outcome

    monkeypatch.setattr(http.urllib.request, "urlopen", urlopen)

    return calls


#
# Retrying
#


def test_a_rate_limited_call_is_retried(monkeypatch, slept):

    calls = responder(monkeypatch, _build("{}", None), FakeResponse(b"ok"))

    assert http.request("https://example.test") == b"ok"

    assert calls["count"] == 2


def test_it_waits_as_long_as_dropbox_asked(monkeypatch, slept):
    """
    The number lives inside the error document, not only the header.
    """

    responder(monkeypatch, rate_limited(retry_after=3), FakeResponse(b"ok"))

    http.request("https://example.test")

    assert slept == [3.0]


def test_a_retry_after_header_is_honoured(monkeypatch, slept):

    responder(monkeypatch, _build("{}", 5), FakeResponse(b"ok"))

    http.request("https://example.test")

    assert slept == [5.0]


def test_a_wait_is_never_unbounded(monkeypatch, slept):
    """
    A save transfer that pauses for an hour has stopped transferring.
    """

    responder(monkeypatch, rate_limited(retry_after=9000), FakeResponse(b"ok"))

    http.request("https://example.test")

    assert slept == [http.MAX_RETRY_WAIT]


def test_zero_still_means_not_right_now(monkeypatch, slept):

    responder(monkeypatch, rate_limited(retry_after=0), FakeResponse(b"ok"))

    http.request("https://example.test")

    assert slept == [http.DEFAULT_RETRY_WAIT]


def test_it_gives_up_eventually(monkeypatch, slept):
    """
    A provider that never relents is a failure like any other.
    """

    responder(monkeypatch, *[rate_limited() for _ in range(10)])

    with pytest.raises(http.HttpError) as raised:
        http.request("https://example.test", attempts=3)

    assert raised.value.status == 429

    assert len(slept) == 2


#
# What must not be retried
#


def test_other_failures_are_raised_at_once(monkeypatch, slept):

    calls = responder(monkeypatch, _build("server broke", status=500))

    with pytest.raises(http.HttpError):
        http.request("https://example.test")

    assert calls["count"] == 1

    assert slept == []


def test_a_probe_never_waits(monkeypatch, slept):
    """
    Being told to slow down already answers "are you reachable".

    A launch waits on that question, so the probe must not turn a rate
    limit into the delay it exists to avoid.
    """

    calls = responder(monkeypatch, *[rate_limited() for _ in range(5)])

    with pytest.raises(http.HttpError):
        http.request("https://example.test", attempts=1)

    assert calls["count"] == 1

    assert slept == []
