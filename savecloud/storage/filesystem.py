"""
Filesystem storage backend.

Any storage provider that presents itself as a directory - a plain
folder, a Syncthing share, a mounted network drive, a synchronized
cloud folder - shares the same synchronization logic. Concrete
backends only need to supply a root directory and an availability
check.

Remote layout::

    <root>/
        games/
            <game-id>/
                current/
                versions/
                manifest.json
                runtime.json
                state.json
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from savecloud.config import layout
from savecloud.models.game import Game
from savecloud.models.remote_state import RemoteState
from savecloud.storage.base import BaseStorageBackend
from savecloud.utils.filesystem import remove_directory, replace_directory
from savecloud.utils.hashing import hash_directory


class FilesystemStorageBackend(BaseStorageBackend):
    """
    Synchronize the library against a directory tree.
    """

    #
    # Subclasses must implement storage_root().
    #

    @classmethod
    def storage_root(cls) -> Path:
        """
        Return the backend's root directory.
        """

        raise NotImplementedError

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    @classmethod
    def games_directory(cls) -> Path:
        """Return the directory holding every remote game."""
        return cls.storage_root() / "games"

    @classmethod
    def game_directory(
        cls,
        game_id: str,
    ) -> Path:
        """Return a game's remote directory."""
        return cls.games_directory() / game_id

    @classmethod
    def current_directory(
        cls,
        game_id: str,
    ) -> Path:
        """Return a game's remote current save directory."""
        return cls.game_directory(game_id) / "current"

    @classmethod
    def versions_directory(
        cls,
        game_id: str,
    ) -> Path:
        """Return a game's remote version directory."""
        return cls.game_directory(game_id) / "versions"

    @classmethod
    def state_path(
        cls,
        game_id: str,
    ) -> Path:
        """Return a game's remote state document path."""
        return cls.game_directory(game_id) / "state.json"

    @classmethod
    def ensure_game_directory(
        cls,
        game_id: str,
    ) -> Path:
        """
        Create a game's remote directory if necessary.
        """

        directory = cls.game_directory(game_id)

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        return directory

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @classmethod
    def available(cls) -> bool:
        """
        Return True if the storage root is usable.
        """

        root = cls.storage_root()

        try:
            root.mkdir(
                parents=True,
                exist_ok=True,
            )

        except OSError:
            return False

        return root.is_dir()

    @classmethod
    def unavailable_reason(cls) -> str:
        """
        Explain why the storage root is unusable.
        """

        return f"Storage root is not writable: {cls.storage_root()}"

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @classmethod
    def exists(
        cls,
        game_id: str,
    ) -> bool:
        """
        Return True if the backend holds a save for this game.
        """

        return cls.current_directory(game_id).exists()

    @classmethod
    def state(
        cls,
        game_id: str,
    ) -> RemoteState | None:
        """
        Return the recorded remote state for a game.
        """

        path = cls.state_path(game_id)

        if not path.exists():
            return None

        try:
            with path.open("r", encoding="utf-8") as file:
                return RemoteState.from_dict(json.load(file))

        except (json.JSONDecodeError, OSError, KeyError):
            return None

    @classmethod
    def list_games(cls) -> list[str]:
        """
        Return every game ID held by the backend.
        """

        games = cls.games_directory()

        if not games.exists():
            return []

        return sorted(
            directory.name
            for directory in games.iterdir()
            if directory.is_dir() and (directory / "current").exists()
        )

    @classmethod
    def metadata(
        cls,
        game_id: str,
    ) -> dict:
        """
        Return metadata describing the remote save.
        """

        state = cls.state(game_id)

        if state is None:
            raise FileNotFoundError(
                f"Remote save does not exist: {cls.game_directory(game_id)}",
            )

        return state.to_dict()

    # ------------------------------------------------------------------
    # Transfer
    # ------------------------------------------------------------------

    @classmethod
    def upload(
        cls,
        game: Game,
    ) -> RemoteState:
        """
        Upload a game's library entry.
        """

        game_id = game.manifest.game_id

        source = layout.current_directory(game_id)

        if not source.exists():
            raise FileNotFoundError(
                f"Managed save directory does not exist: {source}",
            )

        cls.ensure_game_directory(game_id)

        #
        # Current save.
        #

        replace_directory(
            source,
            cls.current_directory(game_id),
        )

        #
        # Version history. Versions are immutable, so anything already
        # present remotely is already correct and is not re-uploaded.
        #

        cls._push_versions(game_id)

        #
        # Synchronized registry documents. These are what allow another
        # device to adopt the game without registering it again.
        #

        cls._copy_file(
            layout.manifest_path(game_id),
            cls.game_directory(game_id) / "manifest.json",
        )

        cls._copy_file(
            layout.runtime_path(game_id),
            cls.game_directory(game_id) / "runtime.json",
        )

        #
        # Remote state.
        #

        state = RemoteState.create(
            game_id=game_id,
            checksum=hash_directory(source),
            version=game.runtime.current_version,
            device_id=game.runtime.last_device or "",
            device_name="",
        )

        cls._write_state(game_id, state)

        return state

    @classmethod
    def download(
        cls,
        game_id: str,
    ) -> RemoteState:
        """
        Download a game's library entry.
        """

        source = cls.current_directory(game_id)

        if not source.exists():
            raise FileNotFoundError(
                f"Remote save directory does not exist: {source}",
            )

        replace_directory(
            source,
            layout.current_directory(game_id),
        )

        cls._pull_versions(game_id)

        #
        # Registry documents are only adopted when the remote actually
        # has them; an older upload may predate registry sync.
        #

        cls._copy_file(
            cls.game_directory(game_id) / "manifest.json",
            layout.manifest_path(game_id),
        )

        cls._copy_file(
            cls.game_directory(game_id) / "runtime.json",
            layout.runtime_path(game_id),
        )

        state = cls.state(game_id)

        if state is None:
            #
            # A remote written by an older version, or by a plain file
            # copy, has no state document. Derive one so that conflict
            # detection has something to compare against.
            #

            state = RemoteState.create(
                game_id=game_id,
                checksum=hash_directory(source),
                version=0,
                device_id="",
                device_name="",
            )

        return state

    @classmethod
    def fetch_current(
        cls,
        game_id: str,
        destination: Path,
    ) -> RemoteState:
        """
        Copy only the remote current save to ``destination``.
        """

        source = cls.current_directory(game_id)

        if not source.exists():
            raise FileNotFoundError(
                f"Remote save directory does not exist: {source}",
            )

        replace_directory(
            source,
            Path(destination),
        )

        state = cls.state(game_id)

        if state is None:
            state = RemoteState.create(
                game_id=game_id,
                checksum=hash_directory(source),
                version=0,
                device_id="",
                device_name="",
            )

        return state

    @classmethod
    def delete(
        cls,
        game_id: str,
    ) -> None:
        """
        Remove a game from the backend.
        """

        remove_directory(
            cls.game_directory(game_id),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @classmethod
    def _write_state(
        cls,
        game_id: str,
        state: RemoteState,
    ) -> None:
        """
        Persist the remote state document.
        """

        with cls.state_path(game_id).open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                state.to_dict(),
                file,
                indent=4,
            )

    @staticmethod
    def _copy_file(
        source: Path,
        destination: Path,
    ) -> None:
        """
        Copy a file when it exists.
        """

        if not source.exists():
            return

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

    @classmethod
    def _push_versions(
        cls,
        game_id: str,
    ) -> None:
        """
        Copy local versions that the backend does not already hold.
        """

        cls._sync_versions(
            layout.versions_directory(game_id),
            cls.versions_directory(game_id),
        )

    @classmethod
    def _pull_versions(
        cls,
        game_id: str,
    ) -> None:
        """
        Copy remote versions that this device does not already hold.
        """

        cls._sync_versions(
            cls.versions_directory(game_id),
            layout.versions_directory(game_id),
        )

    @staticmethod
    def _sync_versions(
        source: Path,
        destination: Path,
    ) -> None:
        """
        Copy version directories that are missing from the destination.

        Versions are immutable, so an existing directory is never
        overwritten.
        """

        if not source.exists():
            return

        destination.mkdir(
            parents=True,
            exist_ok=True,
        )

        for directory in sorted(source.iterdir()):

            if not directory.is_dir():
                continue

            target = destination / directory.name

            if target.exists():
                continue

            shutil.copytree(
                directory,
                target,
            )
