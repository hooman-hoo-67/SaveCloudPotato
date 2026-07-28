"""
SaveCloud launcher framework.
"""

from savecloud.launchers.appimage import AppImageLauncher
from savecloud.launchers.native import NativeLauncher
from savecloud.launchers.registry import LauncherRegistry
from savecloud.launchers.steam import SteamLauncher

__all__ = [
    "LauncherRegistry",
    "NativeLauncher",
    "AppImageLauncher",
    "SteamLauncher",
]
