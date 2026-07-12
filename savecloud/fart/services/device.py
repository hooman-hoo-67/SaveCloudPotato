"""
Device-specific profile management for SaveCloud.

The DeviceService manages local device profiles.

Unlike the registry, device profiles are never synchronized between
devices.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from savecloud.config.constants import DEVICE_DIR
from savecloud.models.device_profile import DeviceProfile


class DeviceService:
    """Manage local device profiles."""

    @staticmethod
    def device_directory(device_id: str) -> Path:
        """
        Return the directory for a device.
        """
        return DEVICE_DIR / device_id

    @staticmethod
    def profile_path(
        device_id: str,
        game_id: str,
    ) -> Path:
        """
        Return the profile path for a game on a device.
        """
        return DeviceService.device_directory(device_id) / f"{game_id}.json"

    @staticmethod
    def exists(
        device_id: str,
        game_id: str,
    ) -> bool:
        """
        Return True if the profile exists.
        """
        return DeviceService.profile_path(
            device_id,
            game_id,
        ).exists()

    @staticmethod
    def create_profile(
        profile: DeviceProfile,
    ) -> None:
        """
        Create a device profile.
        """
        DeviceService.save_profile(profile)

    @staticmethod
    def save_profile(
        profile: DeviceProfile,
    ) -> None:
        """
        Save a device profile.
        """

        DeviceService.device_directory(profile.device_id).mkdir(
            parents=True,
            exist_ok=True,
        )

        data = asdict(profile)

        data["working_save_path"] = str(profile.working_save_path)

        if profile.last_local_sync is not None:
            data["last_local_sync"] = profile.last_local_sync.isoformat()

        with DeviceService.profile_path(
            profile.device_id,
            profile.game_id,
        ).open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                indent=4,
            )

    @staticmethod
    def load_profile(
        device_id: str,
        game_id: str,
    ) -> DeviceProfile:
        """
        Load a device profile.
        """

        with DeviceService.profile_path(
            device_id,
            game_id,
        ).open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        last_local_sync = None

        if data["last_local_sync"] is not None:
            last_local_sync = datetime.fromisoformat(data["last_local_sync"])

        return DeviceProfile(
            device_id=data["device_id"],
            device_name=data["device_name"],
            game_id=data["game_id"],
            working_save_path=Path(data["working_save_path"]),
            launch_command=data["launch_command"],
            last_local_sync=last_local_sync,
            enabled=data["enabled"],
        )

    @staticmethod
    def delete_profile(
        device_id: str,
        game_id: str,
    ) -> None:
        """
        Delete a device profile.
        """

        profile = DeviceService.profile_path(
            device_id,
            game_id,
        )

        if profile.exists():
            profile.unlink()

        device_directory = DeviceService.device_directory(device_id)

        if device_directory.exists() and not any(device_directory.iterdir()):
            shutil.rmtree(device_directory)
