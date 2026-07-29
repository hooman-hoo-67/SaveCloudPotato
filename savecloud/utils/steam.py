"""
Steam installation discovery.

Both the Proton adapter and the Steam launcher need to know where Steam
is and what it has installed. Frameworks never import one another, so
that shared knowledge lives here.

Everything is a lookup against the filesystem. Nothing here launches
anything, reads a save, or writes to Steam's configuration.
"""

from __future__ import annotations

import os
from pathlib import Path

from savecloud.utils import vdf

#
# Locations Steam installs itself to on Linux, most conventional
# first. `~/.steam/steam` is a symlink Steam maintains, so it usually
# resolves to one of the others.
#

STEAM_ROOTS = (
    "~/.steam/steam",
    "~/.steam/root",
    "~/.local/share/Steam",
    "~/.var/app/com.valvesoftware.Steam/data/Steam",
)

#
# Environment override, mostly for testing and unusual installs.
#

STEAM_ROOT_ENV = "SAVECLOUD_STEAM_ROOT"

#
# Directories a Windows game is likely to keep saves in, relative to
# the Proton prefix's user directory. Ordered so the most common comes
# first.
#

PREFIX_SAVE_LOCATIONS = (
    "AppData/Roaming",
    "AppData/Local",
    "AppData/LocalLow",
    "Documents/My Games",
    "Documents",
    "Saved Games",
)


def steam_root() -> Path | None:
    """
    Return Steam's installation directory.

    Returns None when Steam is not installed.
    """

    override = os.environ.get(STEAM_ROOT_ENV)

    if override:
        path = Path(override).expanduser()

        return path if path.is_dir() else None

    for candidate in STEAM_ROOTS:

        path = Path(candidate).expanduser()

        #
        # `~/.steam/steam` is a symlink. Resolve it so two candidates
        # pointing at the same install do not look like two libraries.
        #

        if path.is_dir():
            return path.resolve()

    return None


def library_folders() -> list[Path]:
    """
    Return every Steam library directory.

    A library is a directory containing `steamapps`. Steam records
    additional ones - second drives, SD cards - in libraryfolders.vdf.
    """

    root = steam_root()

    if root is None:
        return []

    libraries: list[Path] = []

    def add(path: Path) -> None:
        resolved = path.resolve()

        if (resolved / "steamapps").is_dir() and resolved not in libraries:
            libraries.append(resolved)

    add(root)

    manifest = root / "steamapps" / "libraryfolders.vdf"

    if not manifest.exists():
        return libraries

    data = vdf.load(manifest)

    folders = data.get("libraryfolders", data.get("LibraryFolders", {}))

    if not isinstance(folders, dict):
        return libraries

    for value in folders.values():

        #
        # Modern Steam nests each library in a block with a "path".
        # Older versions mapped an index straight to a path string.
        #

        if isinstance(value, dict):
            path = value.get("path")

        elif isinstance(value, str):
            path = value

        else:
            continue

        if path:
            add(Path(path).expanduser())

    return libraries


def installed_apps() -> dict[str, str]:
    """
    Return installed Steam applications as {app_id: name}.

    Reads the appmanifest files Steam writes beside each library.
    """

    apps: dict[str, str] = {}

    for library in library_folders():

        steamapps = library / "steamapps"

        try:
            manifests = sorted(steamapps.glob("appmanifest_*.acf"))

        except OSError:
            continue

        for manifest in manifests:

            data = vdf.load(manifest).get("AppState")

            if not isinstance(data, dict):
                continue

            app_id = data.get("appid")

            if not app_id:
                continue

            apps[str(app_id)] = data.get("name", f"App {app_id}")

    return apps


def app_name(app_id: str) -> str | None:
    """
    Return an installed application's name.
    """

    return installed_apps().get(str(app_id))


def compat_prefix(app_id: str) -> Path | None:
    """
    Return the Proton prefix directory for an application.

    This is the `pfx` directory holding the emulated Windows drive. It
    exists only once the game has been run at least once under Proton.
    """

    for library in library_folders():

        prefix = library / "steamapps" / "compatdata" / str(app_id) / "pfx"

        if prefix.is_dir():
            return prefix

    return None


def prefix_user_directory(app_id: str) -> Path | None:
    """
    Return the Windows user directory inside a Proton prefix.

    This is where nearly every Windows game keeps its saves.
    """

    prefix = compat_prefix(app_id)

    if prefix is None:
        return None

    users = prefix / "drive_c" / "users"

    if not users.is_dir():
        return None

    #
    # Proton normally creates "steamuser". Older prefixes used the
    # host account name, so fall back to whatever single user exists.
    #

    steamuser = users / "steamuser"

    if steamuser.is_dir():
        return steamuser

    candidates = [
        path
        for path in sorted(users.iterdir())
        if path.is_dir() and path.name not in {"Public", "All Users"}
    ]

    if len(candidates) == 1:
        return candidates[0]

    return None


#
# How far into a candidate to look when judging it. A save directory
# is small; a directory holding thousands of files is something else,
# and walking all of it to find that out would be the expensive way to
# learn nothing.
#

CANDIDATE_SCAN_LIMIT = 200


def candidate_save_directories(app_id: str) -> list[Path]:
    """
    Return plausible save directories inside an application's prefix.

    Windows games have no single convention, so this reports what
    exists rather than guessing which one is correct. The caller is
    expected to let the user choose.

    Ordered by how recently something inside was written. A game that
    has just been played has touched its save, so the newest directory
    is the best guess available - and a better one than the order
    these locations happen to be listed in, which is what "first in
    the list" would otherwise mean.
    """

    user_directory = prefix_user_directory(app_id)

    if user_directory is None:
        return []

    #
    # Some scan locations nest inside others - Documents/My Games sits
    # inside Documents - so a container would otherwise be offered as
    # though it were a save directory.
    #

    scanned = {
        user_directory / relative for relative in PREFIX_SAVE_LOCATIONS
    }

    candidates: list[Path] = []

    for relative in PREFIX_SAVE_LOCATIONS:

        base = user_directory / relative

        if not base.is_dir():
            continue

        try:
            children = sorted(path for path in base.iterdir() if path.is_dir())

        except OSError:
            continue

        for child in children:

            if child in scanned or child in candidates:
                continue

            candidates.append(child)

    #
    # Empty directories sort last however new they are: a game leaves
    # them behind on first launch, before there is anything to save.
    #

    return sorted(
        candidates,
        key=lambda path: (0, 0.0) if is_empty(path) else (1, last_written(path)),
        reverse=True,
    )


def is_empty(directory: Path) -> bool:
    """
    Return whether a directory holds no files at any depth.
    """

    return last_written(directory) == 0.0


def last_written(directory: Path) -> float:
    """
    Return when a file inside a directory was most recently written.

    Zero when it holds no files. Directory timestamps are ignored:
    they move when anything is created beside the save, which makes an
    untouched folder look freshly used.
    """

    newest = 0.0

    seen = 0

    for path in directory.rglob("*"):

        if seen >= CANDIDATE_SCAN_LIMIT:
            break

        try:
            if not path.is_file():
                continue

            seen += 1

            newest = max(newest, path.stat().st_mtime)

        except OSError:
            continue

    return newest


def is_steam_deck() -> bool:
    """
    Return True when running on a Steam Deck.

    SteamOS identifies itself in os-release; the hardware also has a
    predictable user account.
    """

    try:
        release = Path("/etc/os-release").read_text(encoding="utf-8")

    except OSError:
        return False

    return "steamdeck" in release.lower()
