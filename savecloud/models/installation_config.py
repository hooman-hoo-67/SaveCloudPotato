"""
Installation-wide configuration.

Unlike the GameManifest, which describes a single game, the
InstallationConfig describes the SaveCloud installation itself.

It is stored in config.json and is never synchronized between devices.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from savecloud.config.constants import default_storage_root


@dataclass(slots=True)
class InstallationConfig:
    """
    Settings that apply to every game managed by this installation.
    """

    #
    # Which storage backend synchronizes the library.
    #

    storage_backend: str = "local"

    #
    # Where that backend keeps its data.
    #

    storage_root: Path = None  # type: ignore[assignment]

    def __post_init__(self) -> None:

        if self.storage_root is None:
            self.storage_root = default_storage_root()

        if not isinstance(self.storage_root, Path):
            self.storage_root = Path(self.storage_root).expanduser()

    def to_dict(self) -> dict:
        """
        Convert the configuration to a serializable dictionary.
        """

        return {
            "storage_backend": self.storage_backend,
            "storage_root": str(self.storage_root),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
    ) -> "InstallationConfig":
        """
        Construct a configuration from a dictionary.

        Unknown keys are ignored so that configuration files written by
        newer versions of SaveCloud remain loadable.
        """

        storage_root = data.get("storage_root")

        return cls(
            storage_backend=data.get("storage_backend", "local"),
            storage_root=(Path(storage_root).expanduser() if storage_root else None),
        )
