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
    RUNNING = "running"
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

    last_launch: Optional[datetime] = None

    last_exit: Optional[datetime] = None

    last_exit_code: Optional[int] = None

    status: SyncStatus = SyncStatus.UNKNOWN

    pending_upload: bool = False

    last_error: Optional[str] = None

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def mark_pending(self) -> None:
        """
        Mark the game as having pending changes.
        """

        self.status = SyncStatus.PENDING
        self.pending_upload = True
        self.last_error = None

    def mark_running(self) -> None:
        """
        Mark the game as currently running.
        """

        self.status = SyncStatus.RUNNING
        self.last_launch = datetime.now(UTC)
        self.last_error = None

    def mark_exited(
        self,
        exit_code: int,
    ) -> None:
        """
        Mark the game as exited.
        """

        self.last_exit = datetime.now(UTC)
        self.last_exit_code = exit_code

        #
        # Status will immediately become
        # SYNCED or ERROR depending on
        # the workflow afterwards.
        #

    def mark_synced(
        self,
        device_id: str,
    ) -> None:
        """
        Mark the game as synchronized.
        """

        self.status = SyncStatus.SYNCED
        self.pending_upload = False
        self.last_error = None
        self.last_device = device_id
        self.last_sync = datetime.now(UTC)

    def mark_error(
        self,
        message: str,
    ) -> None:
        """
        Mark the runtime as being in an error state.
        """

        self.status = SyncStatus.ERROR
        self.pending_upload = False
        self.last_error = message

    def mark_conflict(self) -> None:
        """
        Mark the runtime as being in conflict.
        """

        self.status = SyncStatus.CONFLICT


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
