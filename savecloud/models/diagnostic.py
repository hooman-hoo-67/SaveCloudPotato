"""
Diagnostic findings.

A finding describes one thing that is wrong, or worth knowing, about an
installation. Findings carry a remedy wherever one exists, because a
diagnosis the user cannot act on is not much use.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Optional


class Severity(StrEnum):
    """
    How much a finding matters.
    """

    #
    # Confirmation that something is set up correctly. Reported so the
    # user can see what was actually checked.
    #

    OK = "ok"

    #
    # Something is not right but SaveCloud still works. A pending
    # upload, a replication conflict, a save waiting to be pushed.
    #

    WARNING = "warning"

    #
    # Something is broken. A missing library, an unreachable backend,
    # a launch command that no longer exists.
    #

    ERROR = "error"


@dataclass(slots=True)
class Finding:
    """
    One diagnostic result.
    """

    severity: Severity

    #
    # Short description of what was checked.
    #

    title: str

    #
    # What was found.
    #

    detail: str = ""

    #
    # What the user can do about it.
    #

    remedy: Optional[str] = None

    #
    # Which game this concerns, when it concerns one.
    #

    game_id: Optional[str] = None

    @property
    def is_problem(self) -> bool:
        """
        Return True if this finding represents something wrong.
        """

        return self.severity is not Severity.OK
