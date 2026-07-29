"""
Progress reporting.

A directory copy is effectively instant, so the filesystem backends
never needed to say anything. A cloud backend spends one network round
trip per file, which turns the same operation into minutes of silence -
indistinguishable from a hang.

Backends report progress here. Whether anything is displayed is the
command layer's decision, so nothing below the CLI has to know whether
it is running interactively.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

#
# Installed by the command layer. None means report nothing, which is
# what services and tests get.
#

_reporter: Optional[Callable[[str], None]] = None


def set_reporter(reporter: Optional[Callable[[str], None]]) -> None:
    """
    Install the function that displays progress.
    """

    global _reporter

    _reporter = reporter


def reporter() -> Optional[Callable[[str], None]]:
    """
    Return the installed reporter, if any.
    """

    return _reporter


def report(message: str) -> None:
    """
    Report a step. Silent unless a reporter is installed.
    """

    if _reporter is not None:
        _reporter(message)


class Progress:
    """
    Reports "doing X (3/12)" while working through a known total.

    Safe to step from several threads, since transfers run in parallel
    and two workers finishing at once must not lose a count or
    interleave a line.
    """

    def __init__(
        self,
        label: str,
        total: int,
    ) -> None:

        self.label = label
        self.total = total
        self.done = 0

        self._lock = threading.Lock()

    def step(self, detail: str = "") -> None:
        """
        Record one completed unit.
        """

        with self._lock:

            self.done += 1

            done = self.done

            if self.total <= 1 and not detail:
                return

            suffix = f" {detail}" if detail else ""

            report(f"{self.label} ({done}/{self.total}){suffix}")
