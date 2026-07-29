# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build for SaveCloud.

One binary containing both the command line and the interface, since
Steam launch options and an application menu have to point at the same
file.
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent

sys.path.insert(0, str(ROOT))

#
# Qt is large and only some of it is used. Excluding what SaveCloud
# never imports keeps the artifact to something worth downloading.
#

EXCLUDED = [
    "PySide6.Qt3DAnimation",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "tkinter",
]

analysis = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    #
    # Commands and backends are reached through registries rather than
    # imported by name, so PyInstaller cannot see them.
    #
    hiddenimports=[
        "savecloud.adapters.eden",
        "savecloud.adapters.manual",
        "savecloud.adapters.steam_proton",
        "savecloud.launchers.appimage",
        "savecloud.launchers.native",
        "savecloud.launchers.steam",
        "savecloud.storage.dropbox",
        "savecloud.storage.local",
        "savecloud.storage.syncthing",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDED,
    noarchive=False,
)

archive = PYZ(analysis.pure)

executable = EXE(
    archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="savecloud",
    debug=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="savecloud",
)
