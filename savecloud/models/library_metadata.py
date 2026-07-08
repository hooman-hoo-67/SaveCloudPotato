"""
Library metadata model.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class LibraryMetadata:
    """
    Metadata stored for a game's managed library.
    """

    current_version: int

    latest_version: int

    created_at: str

    last_import: str | None

    last_export: str | None

    def to_dict(self) -> dict:
        """
        Convert the metadata to a dictionary.
        """

        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        data: dict,
    ) -> "LibraryMetadata":
        """
        Construct metadata from a dictionary.
        """

        return cls(**data)
