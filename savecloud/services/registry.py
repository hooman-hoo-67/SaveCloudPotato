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

from savecloud.config.constants import REGISTRY_DIR
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
        return REGISTRY_DIR / game_id

    @staticmethod
    def registry_manifest_path(game_id: str) -> Path:
        """Return the manifest.json path."""
        return RegistryService.registry_directory(game_id) / "manifest.json"

    @staticmethod
    def registry_runtime_path(game_id: str) -> Path:
        """Return the runtime.json path."""
        return RegistryService.registry_directory(game_id) / "runtime.json"

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
            storage_backend=manifest_data["storage_backend"],
            backup_enabled=manifest_data["backup_enabled"],
            sync_enabled=manifest_data["sync_enabled"],
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

        if not REGISTRY_DIR.exists():
            return games

        for directory in sorted(REGISTRY_DIR.iterdir()):
            if not directory.is_dir():
                continue

            games.append(RegistryService.load_game(directory.name))

        return games

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

        if runtime_data["last_sync"] is not None:
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
