"""
Remote synchronization state.

Every storage backend records a small state document alongside the
uploaded save. It describes what the remote currently holds, which is
what allows SaveCloud to detect conflicts without downloading the save
itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class RemoteState:
    """
    Describes the save currently stored by a backend.
    """

    game_id: str

    #
    # Checksum of the uploaded save contents.
    #

    checksum: str

    #
    # Library version the upload corresponds to.
    #

    version: int

    #
    # Which device performed the upload.
    #

    device_id: str
    device_name: str

    updated_at: str

    @classmethod
    def create(
        cls,
        game_id: str,
        checksum: str,
        version: int,
        device_id: str,
        device_name: str,
    ) -> "RemoteState":
        """
        Create state stamped with the current time.
        """

        return cls(
            game_id=game_id,
            checksum=checksum,
            version=version,
            device_id=device_id,
            device_name=device_name,
            updated_at=datetime.now(UTC).isoformat(),
        )

    def to_dict(self) -> dict:
        """
        Convert the state to a serializable dictionary.
        """

        return {
            "game_id": self.game_id,
            "checksum": self.checksum,
            "version": self.version,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
    ) -> "RemoteState":
        """
        Construct state from a dictionary.
        """

        return cls(
            game_id=data["game_id"],
            checksum=data["checksum"],
            version=data.get("version", 0),
            device_id=data.get("device_id", ""),
            device_name=data.get("device_name", ""),
            updated_at=data.get("updated_at", ""),
        )
