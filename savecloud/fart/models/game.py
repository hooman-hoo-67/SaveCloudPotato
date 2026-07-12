"""
Data models representing a game managed by SaveCloud.

These models contain no filesystem or serialization logic.
They are pure data objects used throughout the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Optional

#
# Enumerations
#


class LaunchType(StrEnum):
    """How the game is launched."""

    STEAM = "steam"
    HEROIC = "heroic"
    LUTRIS = "lutris"
    MANUAL = "manual"


class Platform(StrEnum):
    """What kind of game this is."""

    EMULATOR = "emulator"
    PROTON = "proton"
    NATIVE = "native"


class SyncStatus(StrEnum):
    """Current synchronization state."""

    UNKNOWN = "unknown"
    SYNCED = "synced"
    PENDING = "pending"
    CONFLICT = "conflict"
    ERROR = "error"


#
# Game Manifest
#


@dataclass(frozen=True, slots=True)
class GameManifest:
    """
    Configuration describing a managed game.

    This information changes rarely and is synchronized
    between every device.
    """

    game_id: str
    display_name: str

    launch_type: LaunchType
    platform: Platform

    adapter: str
    storage_backend: str

    backup_enabled: bool = True
    sync_enabled: bool = True


#
# Runtime
#


@dataclass(slots=True)
class GameRuntime:
    """
    Runtime information for a managed game.

    This information changes frequently while the game
    is being synchronized.
    """

    current_version: int = 0

    last_device: Optional[str] = None

    last_sync: Optional[datetime] = None

    status: SyncStatus = SyncStatus.UNKNOWN

    pending_upload: bool = False

    last_error: Optional[str] = None

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


#
# Game
#


@dataclass(slots=True)
class Game:
    """
    Represents a complete SaveCloud game.
    """

    manifest: GameManifest
    runtime: GameRuntime
