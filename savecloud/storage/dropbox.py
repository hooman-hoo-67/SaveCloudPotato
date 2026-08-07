"""
Dropbox storage backend.

Unlike the filesystem backends, Dropbox is reached over HTTP, so this
implements BaseStorageBackend directly rather than reusing
FilesystemStorageBackend. The remote layout is deliberately identical,
so a library synchronized through Dropbox is arranged the same way as
one synchronized through a shared folder:

    <root>/games/<game-id>/current/...
                          /versions/000001/...
                          /manifest.json
                          /runtime.json
                          /state.json

Authentication uses a refresh token. Dropbox access tokens expire after
a few hours, so storing one would mean re-authorizing every session;
the refresh token does not expire and is exchanged for an access token
as needed. Credentials live in `providers/dropbox.json`, which is never
synchronized.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Sequence

from savecloud.config import layout
from savecloud.models.game import Game
from savecloud.models.remote_state import RemoteState
from savecloud.services.configuration import ConfigurationService
from savecloud.services.credentials import CredentialService
from savecloud.services.library import SaveCloudLibrary
from savecloud.storage.base import BaseStorageBackend
from savecloud.utils import http
from savecloud.utils.filesystem import remove_directory, replace_directory
from savecloud.utils.hashing import hash_directory
from savecloud.utils.progress import Progress, report

PROVIDER = "dropbox"

API = "https://api.dropboxapi.com/2"
CONTENT = "https://content.dropboxapi.com/2"
TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"
AUTHORIZE_URL = "https://www.dropbox.com/oauth2/authorize"

#
# Dropbox rejects a single-request upload above 150 MB. Saves are far
# smaller, but refusing clearly beats a truncated upload.
#

MAX_UPLOAD_BYTES = 150 * 1024 * 1024

#
# Refresh slightly early rather than discovering expiry mid-transfer.
#

TOKEN_EXPIRY_MARGIN = 120

#
# Each file costs a full round trip, and a save is many small files, so
# the transfer is latency-bound rather than bandwidth-bound. Running
# several at once turns a sum of round trips into roughly the slowest
# of each batch, which is the difference between a minute and a few
# seconds on a Steam Deck's wireless connection.
#
# Kept modest deliberately: Dropbox rate-limits per account, and a
# save is not worth being throttled over.
#

TRANSFER_WORKERS = 8


class DropboxError(RuntimeError):
    """
    A Dropbox operation failed.
    """


def _in_parallel(
    work: "Callable[[Any], None]",
    items: "Sequence[Any]",
) -> None:
    """
    Run ``work`` over ``items`` across a small pool of threads.

    The first failure is raised, after the pool has drained. Failing
    loudly matters more than finishing the rest: a partial upload that
    reported success would leave storage holding a save that never
    existed on any device.

    Short sequences run inline, since a thread pool costs more than a
    round trip saved.
    """

    if not items:
        return

    if len(items) == 1:
        work(items[0])

        return

    workers = min(TRANSFER_WORKERS, len(items))

    with ThreadPoolExecutor(max_workers=workers) as pool:

        futures = [pool.submit(work, item) for item in items]

        failures = [
            future.exception()
            for future in as_completed(futures)
            if future.exception() is not None
        ]

    if failures:
        raise failures[0]


class DropboxClient:
    """
    The subset of the Dropbox API SaveCloud needs.

    Every method takes a Dropbox path (`/SaveCloud/games/...`). Nothing
    here knows what a save is.
    """

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        refresh_token: str,
    ) -> None:

        self.app_key = app_key
        self.app_secret = app_secret
        self.refresh_token = refresh_token

        self._access_token: str | None = None
        self._expires_at: float = 0.0

        #
        # Transfers run in parallel and all share this client. Without
        # the lock, every worker that noticed an expired token would
        # refresh it at once.
        #

        self._token_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def access_token(
        self,
        timeout: int = http.DEFAULT_TIMEOUT,
        attempts: int = http.RETRY_ATTEMPTS,
    ) -> str:
        """
        Return a usable access token, refreshing it if necessary.

        Parameters
        ----------
        timeout
            Seconds to wait. A reachability probe passes a short one,
            since it is only asking whether Dropbox answers at all.
        attempts
            How many times to wait out a rate limit. A probe passes 1:
            being told to slow down already answers the only question
            it asked, and a launch is waiting on the reply.
        """

        with self._token_lock:
            return self._refresh_if_needed(timeout, attempts)

    def _refresh_if_needed(
        self,
        timeout: int,
        attempts: int = http.RETRY_ATTEMPTS,
    ) -> str:
        """
        Return the cached token, refreshing it once if it has expired.
        """

        if self._access_token and time.time() < self._expires_at:
            return self._access_token

        response = http.post_form(
            TOKEN_URL,
            {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.app_key,
                "client_secret": self.app_secret,
            },
            timeout=timeout,
            attempts=attempts,
        )

        token = response.get("access_token")

        if not token:
            raise DropboxError(
                "Dropbox did not return an access token. The refresh "
                "token may have been revoked; re-run "
                "`savecloud config provider dropbox`.",
            )

        self._access_token = token

        self._expires_at = time.time() + int(
            response.get("expires_in", 14400),
        ) - TOKEN_EXPIRY_MARGIN

        return token

    def _auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token()}"}

    # ------------------------------------------------------------------
    # Primitives
    # ------------------------------------------------------------------

    def rpc(
        self,
        endpoint: str,
        payload: dict | None = None,
    ) -> dict:
        """
        Call a JSON endpoint.
        """

        return http.post_json(
            f"{API}/{endpoint}",
            payload,
            headers=self._auth_header(),
        )

    def upload(
        self,
        remote_path: str,
        data: bytes,
    ) -> None:
        """
        Upload a file, overwriting whatever is there.
        """

        if len(data) > MAX_UPLOAD_BYTES:
            raise DropboxError(
                f"{remote_path} is {len(data)} bytes, above Dropbox's "
                f"{MAX_UPLOAD_BYTES} byte single-request limit.",
            )

        headers = self._auth_header()

        headers["Content-Type"] = "application/octet-stream"

        headers["Dropbox-API-Arg"] = json.dumps(
            {
                "path": remote_path,
                "mode": "overwrite",
                "mute": True,
            }
        )

        http.request(
            f"{CONTENT}/files/upload",
            data=data,
            headers=headers,
        )

    def download(
        self,
        remote_path: str,
    ) -> bytes:
        """
        Download a file's contents.
        """

        headers = self._auth_header()

        headers["Dropbox-API-Arg"] = json.dumps({"path": remote_path})

        return http.request(
            f"{CONTENT}/files/download",
            headers=headers,
        )

    def list_folder(
        self,
        remote_path: str,
        recursive: bool = False,
    ) -> list[dict]:
        """
        List a folder's entries, following pagination.

        A missing folder lists as empty rather than raising, since
        "nothing stored yet" is an ordinary state.
        """

        try:
            response = self.rpc(
                "files/list_folder",
                {
                    "path": remote_path,
                    "recursive": recursive,
                },
            )

        except http.HttpError as error:

            if _is_not_found(error):
                return []

            raise

        entries = list(response.get("entries", []))

        while response.get("has_more"):

            response = self.rpc(
                "files/list_folder/continue",
                {"cursor": response["cursor"]},
            )

            entries.extend(response.get("entries", []))

        return entries

    def exists(
        self,
        remote_path: str,
    ) -> bool:
        """
        Return True if a file or folder exists.
        """

        try:
            self.rpc("files/get_metadata", {"path": remote_path})

        except http.HttpError as error:

            if _is_not_found(error):
                return False

            raise

        return True

    def delete(
        self,
        remote_path: str,
    ) -> None:
        """
        Delete a file or folder, tolerating its absence.
        """

        try:
            self.rpc("files/delete_v2", {"path": remote_path})

        except http.HttpError as error:

            if not _is_not_found(error):
                raise

    def account_email(self) -> str | None:
        """
        Return the authenticated account's email, for confirmation.
        """

        try:
            return self.rpc("users/get_current_account").get(
                "email",
            )

        except Exception:
            return None


def _is_not_found(error: http.HttpError) -> bool:
    """
    Return True if a Dropbox error means "that path does not exist".

    Dropbox reports a missing path as 409 with a tagged error body
    rather than 404.
    """

    if error.status not in (404, 409):
        return False

    return "not_found" in error.body


class DropboxStorageBackend(BaseStorageBackend):
    """
    Synchronize the library to Dropbox.
    """

    #
    # Cached so a single command does not re-authenticate per call.
    #

    _client: DropboxClient | None = None

    #
    # Why the last reachability probe failed, so the explanation
    # costs no second round trip.
    #

    _probe_failure: Exception | None = None

    @staticmethod
    def display_name() -> str:
        """
        Human-readable backend name.
        """

        return "Dropbox"

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @classmethod
    def root(cls) -> str:
        """
        Return the configured Dropbox folder holding the library.
        """

        configured = str(ConfigurationService.load().storage_root)

        #
        # storage_root is a filesystem path for other backends. Here it
        # names a folder inside Dropbox, so only the final component is
        # meaningful; an inherited default like /home/you/SaveCloudRemote
        # would otherwise create a nested tree of empty folders.
        #

        name = PurePosixPath(configured).name or "SaveCloud"

        return f"/{name}"

    @classmethod
    def client(cls) -> DropboxClient:
        """
        Return an authenticated client.
        """

        if cls._client is not None:
            return cls._client

        credentials = CredentialService.load(PROVIDER)

        missing = [
            field
            for field in ("app_key", "app_secret", "refresh_token")
            if not credentials.get(field)
        ]

        if missing:
            raise DropboxError(
                f"Dropbox is not set up on this device (missing "
                f"{', '.join(missing)}). Run: "
                f"savecloud config provider dropbox",
            )

        cls._client = DropboxClient(
            credentials["app_key"],
            credentials["app_secret"],
            credentials["refresh_token"],
        )

        return cls._client

    @classmethod
    def reset(cls) -> None:
        """
        Discard the cached client.

        Used after credentials change, and by tests.
        """

        cls._client = None

        cls._probe_failure = None

    # ------------------------------------------------------------------
    # Remote layout
    # ------------------------------------------------------------------

    @classmethod
    def game_path(cls, game_id: str) -> str:
        return f"{cls.root()}/games/{game_id}"

    @classmethod
    def current_path(cls, game_id: str) -> str:
        return f"{cls.game_path(game_id)}/current"

    @classmethod
    def versions_path(cls, game_id: str) -> str:
        return f"{cls.game_path(game_id)}/versions"

    @classmethod
    def state_path(cls, game_id: str) -> str:
        return f"{cls.game_path(game_id)}/state.json"

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @classmethod
    def available(cls) -> bool:
        """
        Return True if Dropbox can be reached with stored credentials.

        Probed with a short timeout and the failure remembered, because
        the caller that gets False almost always asks why immediately
        afterwards. Probing twice would double the wait in front of
        someone whose network is down.
        """

        try:
            cls.client().access_token(
                timeout=http.PROBE_TIMEOUT,
                attempts=1,
            )

        except Exception as error:
            cls._probe_failure = error

            return False

        cls._probe_failure = None

        return True

    @classmethod
    def unavailable_reason(cls) -> str:
        """
        Explain why Dropbox cannot be used.
        """

        if not CredentialService.exists(PROVIDER):
            return (
                "Dropbox is not set up on this device. Run: "
                "savecloud config provider dropbox"
            )

        try:
            if cls._probe_failure is not None:
                raise cls._probe_failure

            cls.client().access_token(
                timeout=http.PROBE_TIMEOUT,
                attempts=1,
            )

        except DropboxError as error:
            return str(error)

        except http.HttpError as error:

            if error.is_auth_failure:
                return (
                    "Dropbox rejected the stored credentials. Re-run: "
                    "savecloud config provider dropbox"
                )

            if error.status == 0:
                return f"Dropbox could not be reached: {error.body}"

            return f"Dropbox returned an error: {error}"

        except Exception as error:
            return f"Dropbox is unavailable: {error}"

        return "Dropbox is unavailable."

    @classmethod
    def requires_setup(cls) -> bool:
        """
        Dropbox needs credentials before it can be used.
        """

        return True

    @classmethod
    def setup(cls) -> None:
        """
        Walk the user through authorizing SaveCloud.
        """

        from savecloud.storage.dropbox_setup import run_setup

        run_setup()

        cls.reset()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @classmethod
    def exists(cls, game_id: str) -> bool:
        """
        Return True if Dropbox holds a save for this game.
        """

        return cls.client().exists(cls.current_path(game_id))

    @classmethod
    def state(cls, game_id: str) -> RemoteState | None:
        """
        Return the recorded remote state for a game.
        """

        try:
            body = cls.client().download(cls.state_path(game_id))

        except http.HttpError as error:

            if _is_not_found(error):
                return None

            raise

        try:
            return RemoteState.from_dict(json.loads(body.decode("utf-8")))

        except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
            return None

    @classmethod
    def list_games(cls) -> list[str]:
        """
        Return every game ID Dropbox holds.
        """

        entries = cls.client().list_folder(f"{cls.root()}/games")

        return sorted(
            entry["name"]
            for entry in entries
            if entry.get(".tag") == "folder"
        )

    @classmethod
    def metadata(cls, game_id: str) -> dict:
        """
        Return metadata describing the remote save.
        """

        state = cls.state(game_id)

        if state is None:
            raise FileNotFoundError(
                f"Dropbox holds no save for {game_id}.",
            )

        return state.to_dict()

    # ------------------------------------------------------------------
    # Transfer
    # ------------------------------------------------------------------

    @classmethod
    def upload(cls, game: Game, history: bool = True) -> RemoteState:
        """
        Upload a game's library entry.
        """

        game_id = game.manifest.game_id

        source = layout.current_directory(game_id)

        if not source.exists():
            raise FileNotFoundError(
                f"Managed save directory does not exist: {source}",
            )

        client = cls.client()

        #
        # Current save. Files are uploaded first, then anything the
        # remote still holds that the save no longer contains is
        # removed, so a partial upload leaves extra files rather than
        # missing ones.
        #

        report("Uploading current save")

        cls._push_directory(client, source, cls.current_path(game_id))

        cls._prune(client, source, cls.current_path(game_id))

        #
        # Version history. Versions are immutable, so any already
        # present remotely is already correct.
        #

        if history:
            cls._push_versions(client, game_id)

        #
        # Registry documents, so another device can adopt the game.
        #

        for name in ("manifest.json", "runtime.json"):

            local = layout.game_registry_directory(game_id) / name

            if local.exists():
                client.upload(
                    f"{cls.game_path(game_id)}/{name}",
                    local.read_bytes(),
                )

        #
        # Named, not just identified. A conflict asks someone to choose
        # between this save and another, and "another device
        # (a3f81c2e)" is not something anyone can weigh against their
        # own machine.
        #

        state = RemoteState.create(
            game_id=game_id,
            checksum=hash_directory(source),
            #
            # The library's count, not the runtime's - see the same
            # call in the filesystem backend.
            #
            version=SaveCloudLibrary.load_library_metadata(
                game_id
            ).latest_version,
            device_id=game.runtime.last_device or "",
            device_name=SaveCloudLibrary.device_name(),
        )

        client.upload(
            cls.state_path(game_id),
            json.dumps(state.to_dict(), indent=4).encode("utf-8"),
        )

        return state

    @classmethod
    def download(cls, game_id: str) -> RemoteState:
        """
        Download a game's library entry.
        """

        client = cls.client()

        if not client.exists(cls.current_path(game_id)):
            raise FileNotFoundError(
                f"Dropbox holds no save for {game_id}.",
            )

        staging = Path(tempfile.mkdtemp(prefix="savecloud-dropbox-"))

        try:
            cls._pull_directory(
                client,
                cls.current_path(game_id),
                staging / "current",
            )

            replace_directory(
                staging / "current",
                layout.current_directory(game_id),
            )

            cls._pull_versions(client, game_id)

            #
            # Registry documents are only adopted when present; an
            # older upload may predate registry synchronization.
            #

            registry = layout.game_registry_directory(game_id)

            for name in ("manifest.json", "runtime.json"):

                try:
                    body = client.download(f"{cls.game_path(game_id)}/{name}")

                except http.HttpError as error:

                    if _is_not_found(error):
                        continue

                    raise

                registry.mkdir(parents=True, exist_ok=True)

                (registry / name).write_bytes(body)

        finally:
            remove_directory(staging)

        state = cls.state(game_id)

        if state is None:
            state = RemoteState.create(
                game_id=game_id,
                checksum=hash_directory(layout.current_directory(game_id)),
                version=0,
                device_id="",
                device_name="",
            )

        return state

    @classmethod
    def fetch_current(
        cls,
        game_id: str,
        destination,
    ) -> RemoteState:
        """
        Copy only the remote current save to an arbitrary location.
        """

        client = cls.client()

        if not client.exists(cls.current_path(game_id)):
            raise FileNotFoundError(
                f"Dropbox holds no save for {game_id}.",
            )

        staging = Path(tempfile.mkdtemp(prefix="savecloud-dropbox-"))

        try:
            cls._pull_directory(
                client,
                cls.current_path(game_id),
                staging / "current",
            )

            replace_directory(staging / "current", Path(destination))

        finally:
            remove_directory(staging)

        state = cls.state(game_id)

        if state is None:
            state = RemoteState.create(
                game_id=game_id,
                checksum=hash_directory(Path(destination)),
                version=0,
                device_id="",
                device_name="",
            )

        return state

    @classmethod
    def delete(cls, game_id: str) -> None:
        """
        Remove a game from Dropbox.
        """

        cls.client().delete(cls.game_path(game_id))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _relative_files(directory: Path) -> list[Path]:
        """
        Return every file beneath a directory, relative to it.
        """

        if not directory.exists():
            return []

        return sorted(
            path.relative_to(directory)
            for path in directory.rglob("*")
            if path.is_file()
        )

    @classmethod
    def _push_directory(
        cls,
        client: DropboxClient,
        source: Path,
        remote_path: str,
        label: str = "Uploading",
    ) -> None:
        """
        Upload every file beneath a local directory.

        Each file costs a round trip, so progress is reported per file
        rather than leaving the caller staring at nothing.
        """

        files = cls._relative_files(source)

        progress = Progress(label, len(files))

        def send(relative: Path) -> None:

            client.upload(
                f"{remote_path}/{relative.as_posix()}",
                (source / relative).read_bytes(),
            )

            progress.step(relative.as_posix())

        _in_parallel(send, files)

    @classmethod
    def _pull_directory(
        cls,
        client: DropboxClient,
        remote_path: str,
        destination: Path,
    ) -> None:
        """
        Download every file beneath a remote directory.
        """

        destination.mkdir(parents=True, exist_ok=True)

        prefix = remote_path.lower() + "/"

        wanted: list[tuple[str, Path]] = []

        for entry in client.list_folder(remote_path, recursive=True):

            if entry.get(".tag") != "file":
                continue

            #
            # Dropbox reports path_lower for matching and path_display
            # for presentation; the relative part is taken from the
            # lowercased form because that is what the prefix matches.
            #

            full = entry.get("path_display") or entry.get("path_lower", "")

            lowered = entry.get("path_lower", full.lower())

            if not lowered.startswith(prefix):
                continue

            relative = full[len(prefix):] if len(full) > len(prefix) else ""

            if not relative:
                continue

            wanted.append((full, destination / relative))

        progress = Progress("Downloading", len(wanted))

        #
        # Directories are created up front rather than inside the
        # workers, so two threads writing into the same new folder
        # cannot race each other creating it.
        #

        for _, target in wanted:
            target.parent.mkdir(parents=True, exist_ok=True)

        def fetch(item: tuple[str, Path]) -> None:

            full, target = item

            target.write_bytes(client.download(full))

            progress.step(target.name)

        _in_parallel(fetch, wanted)

    @classmethod
    def _prune(
        cls,
        client: DropboxClient,
        source: Path,
        remote_path: str,
    ) -> None:
        """
        Delete remote files the local save no longer contains.
        """

        wanted = {
            relative.as_posix() for relative in cls._relative_files(source)
        }

        prefix = remote_path.lower() + "/"

        for entry in client.list_folder(remote_path, recursive=True):

            if entry.get(".tag") != "file":
                continue

            full = entry.get("path_display") or entry.get("path_lower", "")

            lowered = entry.get("path_lower", full.lower())

            if not lowered.startswith(prefix):
                continue

            relative = full[len(prefix):]

            if relative and relative not in wanted:
                client.delete(full)

    @classmethod
    def push_history(
        cls,
        game_id: str,
    ) -> None:
        """
        Upload version history and trim beyond the retention window.
        """

        cls._push_versions(cls.client(), game_id)

    @classmethod
    def _push_versions(
        cls,
        client: DropboxClient,
        game_id: str,
    ) -> None:
        """
        Upload versions Dropbox does not already hold.
        """

        from savecloud.services.configuration import ConfigurationService
        from savecloud.services.library import SaveCloudLibrary

        keep = ConfigurationService.load().version_retention

        retained = SaveCloudLibrary.retained_versions(game_id, keep)

        local_versions = layout.versions_directory(game_id)

        remote_versions = cls.versions_path(game_id)

        existing = {
            entry["name"]
            for entry in client.list_folder(remote_versions)
            if entry.get(".tag") == "folder"
        }

        if local_versions.exists():

            for directory in sorted(local_versions.iterdir()):

                if not directory.is_dir() or directory.name in existing:
                    continue

                #
                # Only versions inside the retention window are pushed,
                # so a device still holding older history does not keep
                # restoring what another device pruned.
                #

                if directory.name not in retained:
                    continue

                cls._push_directory(
                    client,
                    directory,
                    f"{remote_versions}/{directory.name}",
                    label=f"Uploading version {directory.name}",
                )

                existing.add(directory.name)

        #
        # Trim afterwards, so a version uploaded just now counts towards
        # the window rather than being one over it.
        #

        cls._trim_versions(client, game_id, keep, existing)

    @classmethod
    def prune(
        cls,
        game_id: str,
        keep: int,
    ) -> list[str]:
        """
        Delete versions in Dropbox beyond the newest ``keep``.
        """

        if keep <= 0:
            return []

        client = cls.client()

        existing = {
            entry["name"]
            for entry in client.list_folder(cls.versions_path(game_id))
            if entry.get(".tag") == "folder"
        }

        return cls._trim_versions(client, game_id, keep, existing)

    @classmethod
    def _trim_versions(
        cls,
        client: DropboxClient,
        game_id: str,
        keep: int,
        existing: set[str],
    ) -> list[str]:
        """
        Delete all but the newest ``keep`` of ``existing``.

        Takes the listing as an argument so a push, which has just
        enumerated the folder, does not pay for a second listing.
        """

        if keep <= 0:
            return []

        remote_versions = cls.versions_path(game_id)

        doomed = sorted(existing, reverse=True)[keep:]

        for name in doomed:

            client.delete(f"{remote_versions}/{name}")

        return sorted(doomed)

    @classmethod
    def _pull_versions(
        cls,
        client: DropboxClient,
        game_id: str,
    ) -> None:
        """
        Download versions this device does not already hold.
        """

        local_versions = layout.versions_directory(game_id)

        local_versions.mkdir(parents=True, exist_ok=True)

        remote_versions = cls.versions_path(game_id)

        for entry in client.list_folder(remote_versions):

            if entry.get(".tag") != "folder":
                continue

            target = local_versions / entry["name"]

            if target.exists():
                continue

            staging = Path(
                tempfile.mkdtemp(prefix="savecloud-version-"),
            )

            try:
                cls._pull_directory(
                    client,
                    f"{remote_versions}/{entry['name']}",
                    staging / entry["name"],
                )

                shutil.copytree(staging / entry["name"], target)

            finally:
                remove_directory(staging)
