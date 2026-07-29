"""
Finding SaveCloud's own executable.

Steam launch options are handed to Steam, not to a shell that has
sourced anything. A virtual environment's `bin` is not on the PATH
Steam runs with, so a bare `savecloud` there resolves to nothing and
the game fails to start with no explanation.

The absolute path is used instead, resolved on the device the options
are being written for - which is the only device they will ever be
pasted into.
"""

from __future__ import annotations

import os
import shutil
import shlex
import sys
from pathlib import Path

NAME = "savecloud"


def savecloud_executable() -> Path | None:
    """
    Return the path to this installation's `savecloud` command.

    Returns None when it cannot be found, which happens when SaveCloud
    is being run as a module rather than through its console script.
    """

    #
    # How this process was started, when it was started by the console
    # script. The most direct answer available, and the right one when
    # several installations exist.
    #

    argv0 = sys.argv[0] if sys.argv else ""

    if argv0 and Path(argv0).name in (NAME, f"{NAME}-gui"):

        candidate = Path(argv0).resolve()

        if _runnable(candidate):

            #
            # The interface is a different script beside the same
            # interpreter, so the name has to be corrected.
            #

            return _sibling(candidate) or candidate

    #
    # Beside the interpreter running this. A virtual environment puts
    # both in the same directory, which is the case this exists for.
    #
    # Deliberately not resolved: a virtual environment's `python` is
    # usually a symlink to the system interpreter, and following it
    # lands outside the environment - where SaveCloud is not
    # installed.
    #

    for directory in _script_directories():

        candidate = directory / NAME

        if _runnable(candidate):
            return candidate

    #
    # Anywhere on PATH. Covers a pipx or system installation, where
    # there is no virtual environment to reason about.
    #

    found = shutil.which(NAME)

    return Path(found).resolve() if found else None


def launch_options(game_id: str) -> str:
    """
    The line to paste into a game's Launch Options in Steam.

    Steam replaces `%command%` with the whole real invocation, Proton
    included, so one line covers a native game and a Windows one
    alike.
    """

    executable = savecloud_executable()

    #
    # A bare name is the honest fallback: without a resolved path
    # there is nothing better to offer, and it works wherever
    # SaveCloud happens to be on PATH.
    #

    program = shlex.quote(str(executable)) if executable else NAME

    return f"{program} wrap {game_id} -- %command%"


def _script_directories() -> list[Path]:
    """
    Where this installation keeps its console scripts.

    `sys.prefix` is the environment root whether or not the
    interpreter is a symlink, so it is the reliable one; the
    interpreter's own directory is checked first because it is right
    in the ordinary case and costs nothing.
    """

    directories = [Path(sys.executable).parent]

    prefix = Path(sys.prefix)

    directories.append(prefix / ("Scripts" if os.name == "nt" else "bin"))

    seen: list[Path] = []

    for directory in directories:
        if directory not in seen:
            seen.append(directory)

    return seen


def _runnable(path: Path) -> bool:
    """
    Return whether a path is a file this system would execute.
    """

    return path.is_file() and os.access(path, os.X_OK)


def _sibling(script: Path) -> Path | None:
    """
    Return the `savecloud` command beside another of its scripts.
    """

    candidate = script.parent / NAME

    return candidate if _runnable(candidate) else None
