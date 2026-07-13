"""
SaveCloud launcher framework.
"""

from savecloud.launchers.appimage import AppImageLauncher
from savecloud.launchers.native import NativeLauncher
from savecloud.launchers.registry import LauncherRegistry

__all__ = [
    "LauncherRegistry",
    "NativeLauncher",
    "AppImageLauncher",
]
