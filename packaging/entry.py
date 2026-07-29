"""
Entry point for a packaged build.

One binary has to be both things. Steam launch options invoke it as a
command line - `SaveCloud.AppImage wrap <game> -- %command%` - while
someone opening it from a menu expects a window.

Arguments decide: with them it is the CLI, without them the interface.
That way the same file works in Steam and in an application menu, and
there is only one artifact to install and to point at.
"""

from __future__ import annotations

import multiprocessing
import sys


def main() -> int:
    """
    Dispatch to the interface or the command line.
    """

    #
    # PyInstaller re-executes the bundle for a subprocess, so without
    # this a child would start the whole application again.
    #

    multiprocessing.freeze_support()

    if len(sys.argv) > 1:

        from savecloud.cli import app

        app()

        return 0

    from savecloud.gui.app import main as gui

    return gui()


if __name__ == "__main__":
    raise SystemExit(main())
