"""
Registry management for SaveCloud.

The RegistryService is responsible for creating, loading,
saving, and deleting registered games.

It is the only component that performs filesystem operations
inside the registry directory.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from savecloud.config import layout
from savecloud.config.constants import registry_dir
from savecloud.models.game import (
    Game,
    GameManifest,
    GameRuntime,
    LaunchType,
    Platform,
    SyncStatus,
)


class RegistryService:
    """Manage the SaveCloud registry."""

    @staticmethod
    def registry_directory(game_id: str) -> Path:
        """Return the registry directory for a game."""
        return layout.game_registry_directory(game_id)

    @staticmethod
    def registry_manifest_path(game_id: str) -> Path:
        """Return the manifest.json path."""
        return layout.manifest_path(game_id)

    @staticmethod
    def registry_runtime_path(game_id: str) -> Path:
        """Return the runtime.json path."""
        return layout.runtime_path(game_id)

    @staticmethod
    def exists(game_id: str) -> bool:
        """Return True if the registry exists."""
        return RegistryService.registry_directory(game_id).exists()

    @staticmethod
    def create_registry(game: Game) -> None:
        """
        Create a registry for a game.
        """

        RegistryService.registry_directory(game.manifest.game_id).mkdir(
            parents=True, exist_ok=True
        )

        RegistryService.save_registry_manifest(game.manifest)

        RegistryService.save_runtime(
            game.manifest.game_id,
            game.runtime,
        )

    @staticmethod
    def delete_registry(game_id: str) -> None:
        """
        Delete an entire registry.
        """

        registry = RegistryService.registry_directory(game_id)

        if registry.exists():
            shutil.rmtree(registry)

    @staticmethod
    def save_registry_manifest(
        manifest: GameManifest,
    ) -> None:
        """
        Save a GameManifest to manifest.json.
        """

        RegistryService.registry_directory(manifest.game_id).mkdir(
            parents=True, exist_ok=True
        )

        data = asdict(manifest)

        data["launch_type"] = manifest.launch_type.value
        data["platform"] = manifest.platform.value

        with RegistryService.registry_manifest_path(manifest.game_id).open(
            "w", encoding="utf-8"
        ) as file:
            json.dump(data, file, indent=4)

    @staticmethod
    def save_runtime(
        game_id: str,
        runtime: GameRuntime,
    ) -> None:
        """
        Save a GameRuntime to runtime.json.
        """

        RegistryService.registry_directory(game_id).mkdir(parents=True, exist_ok=True)

        data = asdict(runtime)

        data["status"] = runtime.status.value

        if runtime.last_sync is not None:
            data["last_sync"] = runtime.last_sync.isoformat()

        if runtime.last_launch is not None:
            data["last_launch"] = runtime.last_launch.isoformat()

        if runtime.last_exit is not None:
            data["last_exit"] = runtime.last_exit.isoformat()

        data["created_at"] = runtime.created_at.isoformat()

        with RegistryService.registry_runtime_path(game_id).open(
            "w", encoding="utf-8"
        ) as file:
            json.dump(data, file, indent=4)

    @staticmethod
    def load_manifest(
        game_id: str,
    ) -> GameManifest:
        """
        Load a GameManifest from the registry.

        Manifests written before storage configuration moved into
        InstallationConfig still carry a ``storage_backend`` field. It
        is ignored rather than rejected, so older installations keep
        loading.
        """

        with RegistryService.registry_manifest_path(
            game_id,
        ).open(
            "r",
            encoding="utf-8",
        ) as file:
            manifest_data = json.load(file)

        return GameManifest(
            game_id=manifest_data["game_id"],
            display_name=manifest_data["display_name"],
            launch_type=LaunchType(manifest_data["launch_type"]),
            platform=Platform(manifest_data["platform"]),
            adapter=manifest_data["adapter"],
            backup_enabled=manifest_data.get("backup_enabled", True),
            sync_enabled=manifest_data.get("sync_enabled", True),
        )

    @staticmethod
    def load_game(
        game_id: str,
    ) -> Game:
        """
        Load a Game from the registry.
        """

        manifest = RegistryService.load_manifest(
            game_id,
        )

        runtime = RegistryService.load_runtime(
            game_id,
        )

        return Game(
            manifest=manifest,
            runtime=runtime,
        )

    @staticmethod
    def list_games() -> list[Game]:
        """
        Return all registered games.
        """

        games: list[Game] = []

        registry = registry_dir()

        if not registry.exists():
            return games

        for directory in sorted(registry.iterdir()):
            if not directory.is_dir():
                continue

            if not RegistryService.registry_manifest_path(directory.name).exists():
                continue

            games.append(RegistryService.load_game(directory.name))

        return games

    @staticmethod
    def list_game_ids() -> list[str]:
        """
        Return every registered game ID.
        """

        registry = registry_dir()

        if not registry.exists():
            return []

        return sorted(
            directory.name
            for directory in registry.iterdir()
            if directory.is_dir()
            and RegistryService.registry_manifest_path(directory.name).exists()
        )

    @staticmethod
    def load_runtime(
        game_id: str,
    ) -> GameRuntime:
        """
        Load a GameRuntime from the registry.
        """

        with RegistryService.registry_runtime_path(
            game_id,
        ).open(
            "r",
            encoding="utf-8",
        ) as file:
            runtime_data = json.load(file)

        last_sync = None

        if runtime_data.get("last_sync") is not None:
            last_sync = datetime.fromisoformat(
                runtime_data["last_sync"],
            )

        last_launch = None

        if runtime_data.get("last_launch") is not None:
            last_launch = datetime.fromisoformat(
                runtime_data["last_launch"],
            )

        last_exit = None

        if runtime_data.get("last_exit") is not None:
            last_exit = datetime.fromisoformat(
                runtime_data["last_exit"],
            )

        return GameRuntime(
            current_version=runtime_data["current_version"],
            last_device=runtime_data["last_device"],
            last_sync=last_sync,
            last_launch=last_launch,
            last_exit=last_exit,
            last_exit_code=runtime_data.get("last_exit_code"),
            status=SyncStatus(runtime_data["status"]),
            pending_upload=runtime_data["pending_upload"],
            last_error=runtime_data["last_error"],
            last_sync_checksum=runtime_data.get("last_sync_checksum"),
            created_at=datetime.fromisoformat(
                runtime_data["created_at"],
            ),
        )

    @staticmethod
    def update_runtime(
        game: Game,
    ) -> None:
        """
        Save a game's runtime.
        """

        RegistryService.save_runtime(
            game.manifest.game_id,
            game.runtime,
        )

    @staticmethod
    def legacy_storage_backend() -> str | None:
        """
        Return a storage backend recorded by an older installation.

        Before storage selection moved into InstallationConfig, every
        manifest stored its own backend. This reports the one they
        agree on so it can be adopted as the installation default.

        Returns None when no legacy value exists, or when manifests
        disagree and no single value can be inferred.
        """

        backends: set[str] = set()

        for game_id in RegistryService.list_game_ids():

            try:
                with RegistryService.registry_manifest_path(game_id).open(
                    "r",
                    encoding="utf-8",
                ) as file:
                    data = json.load(file)

            except (json.JSONDecodeError, OSError):
                continue

            backend = data.get("storage_backend")

            if backend:
                backends.add(backend.lower())

        if len(backends) == 1:
            return backends.pop()

        return None
