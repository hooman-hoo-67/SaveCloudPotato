"""
An in-memory stand-in for the Dropbox API.

Implements the handful of endpoints SaveCloud uses, closely enough to
exercise the backend without credentials or a network: paths are
case-insensitive, folders are implied by the files inside them,
listings paginate, and a missing path fails the way Dropbox fails -
409 with a tagged body rather than 404.
"""

from __future__ import annotations

import json

from savecloud.utils import http

TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"
API = "https://api.dropboxapi.com/2"
CONTENT = "https://content.dropboxapi.com/2"


def not_found(path: str) -> http.HttpError:
    """
    Build the error Dropbox returns for a missing path.
    """

    return http.HttpError(
        409,
        json.dumps(
            {"error_summary": f"path/not_found/...{path}"},
        ),
        API,
    )


class FakeDropbox:
    """
    A fake Dropbox account backed by a dictionary.
    """

    #
    # Entries per page, low enough that tests exercise pagination.
    #

    PAGE_SIZE = 3

    def __init__(self) -> None:

        self.files: dict[str, bytes] = {}

        self.email = "player@example.com"

        #
        # Recorded for assertions about what the backend actually did.
        #

        self.uploads: list[str] = []
        self.downloads: list[str] = []
        self.deletes: list[str] = []
        self.token_refreshes = 0

        self._cursors: dict[str, list[dict]] = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def put(self, path: str, data: bytes) -> None:
        """
        Seed a file directly, bypassing the API.
        """

        self.files[path] = data

    def _resolve(self, path: str) -> str | None:
        """
        Return the stored path matching case-insensitively.
        """

        lowered = path.lower()

        for stored in self.files:
            if stored.lower() == lowered:
                return stored

        return None

    def _has_prefix(self, path: str) -> bool:
        prefix = path.rstrip("/").lower() + "/"

        return any(stored.lower().startswith(prefix) for stored in self.files)

    def _entry(self, path: str, tag: str) -> dict:
        return {
            ".tag": tag,
            "name": path.rsplit("/", 1)[-1],
            "path_display": path,
            "path_lower": path.lower(),
        }

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    def list_folder(self, payload: dict) -> dict:

        path = payload["path"].rstrip("/")

        recursive = payload.get("recursive", False)

        if not self._has_prefix(path) and self._resolve(path) is None:
            raise not_found(path)

        prefix = path + "/"

        entries: list[dict] = []

        seen: set[str] = set()

        for stored in sorted(self.files):

            if not stored.lower().startswith(prefix.lower()):
                continue

            rest = stored[len(prefix):]

            if not rest:
                continue

            parts = rest.split("/")

            if not recursive:

                if len(parts) == 1:
                    entries.append(self._entry(stored, "file"))

                else:
                    folder = prefix + parts[0]

                    if folder.lower() not in seen:
                        seen.add(folder.lower())
                        entries.append(self._entry(folder, "folder"))

                continue

            #
            # Recursive listings include the folders along the way,
            # exactly as Dropbox reports them.
            #

            for depth in range(1, len(parts)):

                folder = prefix + "/".join(parts[:depth])

                if folder.lower() not in seen:
                    seen.add(folder.lower())
                    entries.append(self._entry(folder, "folder"))

            entries.append(self._entry(stored, "file"))

        return self._paginate(entries)

    def _paginate(self, entries: list[dict]) -> dict:

        head = entries[: self.PAGE_SIZE]

        tail = entries[self.PAGE_SIZE:]

        if not tail:
            return {"entries": head, "has_more": False, "cursor": ""}

        cursor = f"cursor-{len(self._cursors)}"

        self._cursors[cursor] = tail

        return {"entries": head, "has_more": True, "cursor": cursor}

    def list_folder_continue(self, payload: dict) -> dict:

        return self._paginate(self._cursors.pop(payload["cursor"]))

    def get_metadata(self, payload: dict) -> dict:

        path = payload["path"]

        stored = self._resolve(path)

        if stored is not None:
            return self._entry(stored, "file")

        if self._has_prefix(path):
            return self._entry(path, "folder")

        raise not_found(path)

    def delete_v2(self, payload: dict) -> dict:

        path = payload["path"].rstrip("/")

        prefix = path.lower() + "/"

        doomed = [
            stored
            for stored in self.files
            if stored.lower() == path.lower()
            or stored.lower().startswith(prefix)
        ]

        if not doomed:
            raise not_found(path)

        for stored in doomed:
            del self.files[stored]

        self.deletes.append(path)

        return {}

    def get_current_account(self, payload: dict) -> dict:
        return {"email": self.email}

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def post_form(self, url, fields, headers=None, timeout=None) -> dict:
        """
        Stand in for the OAuth token endpoint.
        """

        assert url == TOKEN_URL, url

        if fields.get("grant_type") == "refresh_token":

            self.token_refreshes += 1

            if fields.get("refresh_token") != "valid-refresh-token":
                raise http.HttpError(
                    400,
                    json.dumps({"error": "invalid_grant"}),
                    url,
                )

            return {"access_token": "an-access-token", "expires_in": 14400}

        if fields.get("grant_type") == "authorization_code":

            if fields.get("code") != "valid-code":
                raise http.HttpError(
                    400,
                    json.dumps({"error": "invalid_grant"}),
                    url,
                )

            return {
                "access_token": "an-access-token",
                "refresh_token": "valid-refresh-token",
                "expires_in": 14400,
            }

        raise AssertionError(f"Unexpected grant: {fields}")

    def post_json(self, url, payload, headers=None, timeout=None) -> dict:
        """
        Stand in for the JSON endpoints.
        """

        endpoint = url[len(API) + 1:]

        handlers = {
            "files/list_folder": self.list_folder,
            "files/list_folder/continue": self.list_folder_continue,
            "files/get_metadata": self.get_metadata,
            "files/delete_v2": self.delete_v2,
            "users/get_current_account": self.get_current_account,
        }

        if endpoint not in handlers:
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        return handlers[endpoint](payload or {})

    def request(self, url, data=None, headers=None, method="POST", timeout=None):
        """
        Stand in for the content endpoints.
        """

        argument = json.loads(headers["Dropbox-API-Arg"])

        path = argument["path"]

        if url == f"{CONTENT}/files/upload":

            self.files[path] = data

            self.uploads.append(path)

            return b"{}"

        if url == f"{CONTENT}/files/download":

            stored = self._resolve(path)

            if stored is None:
                raise not_found(path)

            self.downloads.append(path)

            return self.files[stored]

        raise AssertionError(f"Unexpected content URL: {url}")

    # ------------------------------------------------------------------
    # Installation
    # ------------------------------------------------------------------

    def install(self, monkeypatch) -> "FakeDropbox":
        """
        Route SaveCloud's HTTP helpers at this fake.
        """

        monkeypatch.setattr(http, "post_form", self.post_form)
        monkeypatch.setattr(http, "post_json", self.post_json)
        monkeypatch.setattr(http, "request", self.request)

        return self
