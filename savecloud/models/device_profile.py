"""
Data model representing a device-specific game profile.

A DeviceProfile stores information unique to a single installation of
SaveCloud on a specific machine.

Unlike the GameManifest and GameRuntime, DeviceProfiles are NEVER
synchronized between devices.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class DeviceProfile:
    """
    Device-specific information for a managed game.

    Every registered game has one DeviceProfile per device.
    """

    #
    # Identity
    #

    device_id: str
    device_name: str

    #
    # Association
    #

    game_id: str

    #
    # Local paths
    #

    working_save_path: Path

    #
    # Launch information
    #
    # Optional. A game launched through Steam is started by Steam,
    # which hands SaveCloud the real command through `wrap` - so most
    # games never need one. It is only `savecloud play`, which starts
    # the game itself, that cannot work without it.
    #

    launch_command: str = ""
    launcher: str = "native"
    #
    # Local synchronization state
    #

    last_local_sync: Optional[datetime] = None

    #
    # Whether SaveCloud is enabled for this game
    # on this device.
    #

    enabled: bool = True
