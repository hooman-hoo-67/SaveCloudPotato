"""
Making a downloaded AppImage behave like an installed program.

An AppImage is one file that has been downloaded, not installed. It is
not on PATH, so `savecloud sync` in a terminal finds nothing, and it
has no menu entry, so the only way to open it is to find the file.

This puts both in place, pointing at wherever the file actually is.
Nothing here is required - the AppImage runs perfectly well without
it - so it is offered rather than performed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from savecloud.utils.executable import savecloud_executable

#
# Where a user-level installation goes on Linux. Not chosen: this is
# the XDG layout every desktop already looks in.
#
# It is not necessarily on PATH, which is why `install` checks and says
# so rather than assuming. SteamOS is the case that matters and the
# case that fails - a Steam Deck does not put `~/.local/bin` on PATH,
# so `savecloud` in Konsole finds nothing until a shell profile is
# edited. Steam launch options are unaffected: those name the file
# absolutely and are not run through a login shell.
#

BIN = Path.home() / ".local" / "bin"

COMMAND = BIN / "savecloud"

APPLICATIONS = Path.home() / ".local" / "share" / "applications"

DESKTOP_ENTRY = APPLICATIONS / "savecloud.desktop"

ICONS = Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"

ICON = ICONS / "savecloud.png"


@dataclass(slots=True)
class IntegrationResult:
    """
    What was put in place, and anything the user still has to do.
    """

    ok: bool
    message: str = ""
    created: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def is_packaged() -> bool:
    """
    Return whether this is a downloaded build rather than a checkout.

    A `pip install` already puts `savecloud` on PATH, so there is
    nothing here for it to do.
    """

    return bool(os.environ.get("APPIMAGE"))


def is_installed() -> bool:
    """
    Return whether the command already points at this build.
    """

    executable = savecloud_executable()

    if executable is None or not COMMAND.is_symlink():
        return False

    try:
        return COMMAND.resolve() == executable.resolve()

    except OSError:
        return False


def install() -> IntegrationResult:
    """
    Put `savecloud` on PATH and add a menu entry.

    Returns what was created, and warns rather than fails when the
    desktop cannot be told about it - the command still works.
    """

    executable = savecloud_executable()

    if executable is None:
        return IntegrationResult(
            ok=False,
            message=(
                "SaveCloud could not find its own executable, so there "
                "is nothing to link to."
            ),
        )

    created: list[str] = []

    warnings: list[str] = []

    #
    # The command. A symlink rather than a copy, so replacing the
    # AppImage updates the command too.
    #

    try:
        BIN.mkdir(parents=True, exist_ok=True)

        if COMMAND.is_symlink() or COMMAND.exists():
            COMMAND.unlink()

        COMMAND.symlink_to(executable)

        created.append(str(COMMAND))

    except OSError as error:
        return IntegrationResult(
            ok=False,
            message=f"Could not create {COMMAND}: {error}",
        )

    if not _on_path(BIN):

        profile, line = _shell_profile()

        warnings.append(
            f"{BIN} is not on your PATH, so `savecloud` will not be "
            f"found in a terminal until it is. Add this to {profile}, "
            f"then open a new terminal:\n    {line}"
        )

    #
    # The menu entry. Its Exec has to name the real file: a desktop
    # entry is read by things that do not share this process's PATH.
    #

    try:
        APPLICATIONS.mkdir(parents=True, exist_ok=True)

        DESKTOP_ENTRY.write_text(_desktop_entry(executable), encoding="utf-8")

        created.append(str(DESKTOP_ENTRY))

    except OSError as error:
        warnings.append(f"Could not write a menu entry: {error}")

    icon = _bundled_icon()

    if icon is not None:

        try:
            ICONS.mkdir(parents=True, exist_ok=True)

            ICON.write_bytes(icon.read_bytes())

            created.append(str(ICON))

        except OSError as error:
            warnings.append(f"Could not install the icon: {error}")

    return IntegrationResult(
        ok=True,
        message=f"`savecloud` now runs from {COMMAND}.",
        created=created,
        warnings=warnings,
    )


def remove() -> IntegrationResult:
    """
    Undo what `install` put in place.

    Leaves the AppImage and every save alone: this removes the ways of
    reaching SaveCloud, not SaveCloud.
    """

    removed: list[str] = []

    warnings: list[str] = []

    for path in (COMMAND, DESKTOP_ENTRY, ICON):

        try:
            if path.is_symlink() or path.exists():
                path.unlink()

                removed.append(str(path))

        except OSError as error:
            warnings.append(f"Could not remove {path}: {error}")

    return IntegrationResult(
        ok=True,
        message=(
            "Removed." if removed else "Nothing was installed."
        ),
        created=removed,
        warnings=warnings,
    )


def _on_path(directory: Path) -> bool:
    """
    Return whether a directory is on this process's PATH.
    """

    entries = os.environ.get("PATH", "").split(os.pathsep)

    return any(entry and Path(entry) == directory for entry in entries)


#
# Where a new terminal reads its settings, and how that shell spells
# extending PATH.
#
# "your shell profile" is a category rather than advice, and the
# obvious member of it is usually the wrong one: `~/.bash_profile` is
# read by login shells, while a terminal window opens an interactive
# non-login shell that reads `~/.bashrc` and never looks at the other.
# Someone following the vaguer wording edits the file nothing consults,
# opens a new terminal, and sees no change.
#
# fish is not merely a different file - `export` is not its syntax at
# all, so naming the file without the line would still not work.
#

PROFILES = {
    "bash": ("~/.bashrc", 'export PATH="$HOME/.local/bin:$PATH"'),
    "zsh": ("~/.zshrc", 'export PATH="$HOME/.local/bin:$PATH"'),
    "fish": (
        "~/.config/fish/config.fish",
        "fish_add_path ~/.local/bin",
    ),
}


def _shell_profile() -> tuple[str, str]:
    """
    The file a new terminal will read, and the line to put in it.
    """

    shell = Path(os.environ.get("SHELL", "")).name

    return PROFILES.get(shell, PROFILES["bash"])


def _desktop_entry(executable: Path) -> str:
    """
    Build a desktop entry pointing at a specific file.
    """

    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=SaveCloud\n"
        "GenericName=Save Synchronization\n"
        "Comment=Steam Cloud for everything\n"
        f"Exec={executable}\n"
        "Icon=savecloud\n"
        "Categories=Game;Utility;\n"
        "Terminal=false\n"
    )


def _bundled_icon() -> Path | None:
    """
    Find the icon inside a packaged build.
    """

    import sys

    candidates = [
        Path(getattr(sys, "_MEIPASS", "")) / "savecloud.png",
        Path(__file__).resolve().parent.parent.parent
        / "packaging"
        / "savecloud.png",
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None
