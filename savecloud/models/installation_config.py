"""
Installation configuration model.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class InstallationConfig:
    """
    Installation-wide SaveCloud configuration.
    """

    storage_backend: str = "local"

    storage_root: Path = Path.home() / "SaveCloudRemote"
