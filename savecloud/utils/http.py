"""
Minimal HTTP helpers.

Deliberately built on the standard library. SaveCloud manages save
files, and a dependency that can break an installation is a poor trade
for convenience that urllib already provides.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from savecloud.utils.progress import report

DEFAULT_TIMEOUT = 30

#
# Asking whether a provider is reachable is a different question from
# transferring a save, and deserves a different patience. A launch
# waits on the answer, so the wait has to be short enough that someone
# on a dead network reaches their game rather than concluding it is
# broken.
#

PROBE_TIMEOUT = 5


class HttpError(RuntimeError):
    """
    An HTTP request failed.
    """

    def __init__(
        self,
        status: int,
        body: str,
        url: str,
        retry_after: float | None = None,
    ) -> None:

        super().__init__(f"HTTP {status} from {url}: {body[:400]}")

        self.status = status
        self.body = body
        self.url = url

        #
        # What the response's `Retry-After` header said, if anything.
        # Kept on the error because that is the only place the header
        # survives to.
        #

        self.retry_after = retry_after

    @property
    def is_auth_failure(self) -> bool:
        """
        Return True when the request failed because of credentials.
        """

        return self.status in (401, 403)

    @property
    def is_rate_limited(self) -> bool:
        """
        Return True when the provider asked the caller to slow down.
        """

        return self.status == 429


#
# Being rate limited is not a failure - it is the provider saying
# "later", usually with a number attached. Dropbox returns 429 with
# `too_many_write_operations` whenever several writes land in one
# namespace at once, which is exactly what uploading a save in
# parallel does, and it expects the client to wait and try again.
#
# Reported from a real sync: retry_after of 1 second, and the whole
# transfer failed instead of pausing for it.
#

RETRY_ATTEMPTS = 4

#
# A provider could name any delay. A save transfer that pauses for a
# minute has stopped being a transfer, and a launch is waiting on it.
#

MAX_RETRY_WAIT = 20.0

DEFAULT_RETRY_WAIT = 1.0


def request(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    method: str = "POST",
    timeout: int = DEFAULT_TIMEOUT,
    attempts: int = RETRY_ATTEMPTS,
) -> bytes:
    """
    Perform an HTTP request and return the response body.

    Waits and retries when the provider asks to be slowed down, for as
    long as it keeps asking and there are attempts left.

    Raises
    ------
    HttpError
        For any non-2xx response, carrying the body so a provider can
        explain what went wrong. A 429 that outlasts every attempt is
        raised like any other.
    """

    for attempt in range(1, attempts + 1):

        try:
            return _once(
                url,
                data=data,
                headers=headers,
                method=method,
                timeout=timeout,
            )

        except HttpError as error:

            if not error.is_rate_limited or attempt == attempts:
                raise

            wait = _retry_after(error)

            report(
                f"Rate limited by the provider, waiting {wait:g}s "
                f"(attempt {attempt} of {attempts})"
            )

            time.sleep(wait)

    #
    # Unreachable: the loop either returns or raises.
    #

    raise HttpError(429, "retries exhausted", url)


def _once(
    url: str,
    *,
    data: bytes | None,
    headers: dict[str, str] | None,
    method: str,
    timeout: int,
) -> bytes:
    """
    One attempt, with no retrying.
    """

    call = urllib.request.Request(
        url,
        data=data,
        headers=headers or {},
        method=method,
    )

    try:
        with urllib.request.urlopen(call, timeout=timeout) as response:
            return response.read()

    except urllib.error.HTTPError as error:

        body = ""

        try:
            body = error.read().decode("utf-8", errors="replace")

        except Exception:
            pass

        raise HttpError(
            error.code,
            body,
            url,
            retry_after=_header_seconds(error),
        ) from error

    except urllib.error.URLError as error:
        #
        # No response at all: DNS failure, refused connection, no
        # network. Reported as a status of 0 so callers can treat it
        # like any other failure.
        #

        raise HttpError(0, str(error.reason), url) from error


def _header_seconds(error) -> float | None:
    """
    Read a `Retry-After` header, if the response carried one.
    """

    try:
        value = error.headers.get("Retry-After")

    except Exception:
        return None

    if not value:
        return None

    try:
        return float(value)

    except (TypeError, ValueError):
        #
        # The header may be an HTTP date rather than a count of
        # seconds. Parsing that to fall back on a default we already
        # have is not worth the code.
        #

        return None


def _retry_after(error: HttpError) -> float:
    """
    How long to wait, from whatever the provider was willing to say.

    The header is standard; Dropbox also puts the number inside its
    error document, and does not always send both.
    """

    seconds = error.retry_after

    if seconds is None:

        try:
            document = json.loads(error.body)

            reason = document.get("error", {})

            seconds = reason.get("retry_after")

        except (json.JSONDecodeError, AttributeError, TypeError):
            seconds = None

    try:
        seconds = float(seconds)

    except (TypeError, ValueError):
        seconds = DEFAULT_RETRY_WAIT

    #
    # A provider that says "0" still means "not right now".
    #

    return min(max(seconds, DEFAULT_RETRY_WAIT), MAX_RETRY_WAIT)


def post_json(
    url: str,
    payload: dict | None,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    attempts: int = RETRY_ATTEMPTS,
) -> dict:
    """
    POST a JSON body and decode a JSON response.
    """

    merged = {"Content-Type": "application/json"}

    merged.update(headers or {})

    body = request(
        url,
        data=json.dumps(payload if payload is not None else {}).encode("utf-8"),
        headers=merged,
        timeout=timeout,
        attempts=attempts,
    )

    if not body:
        return {}

    return json.loads(body.decode("utf-8"))


def post_form(
    url: str,
    fields: dict[str, str],
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    attempts: int = RETRY_ATTEMPTS,
) -> dict:
    """
    POST form-encoded fields and decode a JSON response.

    OAuth token endpoints expect this rather than JSON.
    """

    merged = {"Content-Type": "application/x-www-form-urlencoded"}

    merged.update(headers or {})

    body = request(
        url,
        data=urllib.parse.urlencode(fields).encode("utf-8"),
        headers=merged,
        timeout=timeout,
        attempts=attempts,
    )

    if not body:
        return {}

    return json.loads(body.decode("utf-8"))
