"""
Minimal HTTP helpers.

Deliberately built on the standard library. SaveCloud manages save
files, and a dependency that can break an installation is a poor trade
for convenience that urllib already provides.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

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
    ) -> None:

        super().__init__(f"HTTP {status} from {url}: {body[:400]}")

        self.status = status
        self.body = body
        self.url = url

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


def request(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    method: str = "POST",
    timeout: int = DEFAULT_TIMEOUT,
) -> bytes:
    """
    Perform an HTTP request and return the response body.

    Raises
    ------
    HttpError
        For any non-2xx response, carrying the body so a provider can
        explain what went wrong.
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

        raise HttpError(error.code, body, url) from error

    except urllib.error.URLError as error:
        #
        # No response at all: DNS failure, refused connection, no
        # network. Reported as a status of 0 so callers can treat it
        # like any other failure.
        #

        raise HttpError(0, str(error.reason), url) from error


def post_json(
    url: str,
    payload: dict | None,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
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
    )

    if not body:
        return {}

    return json.loads(body.decode("utf-8"))


def post_form(
    url: str,
    fields: dict[str, str],
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
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
    )

    if not body:
        return {}

    return json.loads(body.decode("utf-8"))
