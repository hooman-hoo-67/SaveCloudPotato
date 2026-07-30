"""
A description of one save, for choosing between two of them.

A conflict asks someone to keep one save and discard the other. Two
checksums do not help with that decision: they are equally opaque, and
neither says which machine the other save came from or how long ago
someone was playing on it.

This is what a person can actually weigh - where the save is, when it
was last written, and which version it corresponds to.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class SaveSummary:
    """
    Enough about a save to choose it, or not.
    """

    #
    # Which machine this save belongs to. "This device" for the local
    # side; whatever the other machine calls itself for the remote one.
    #

    where: str

    #
    # When its contents were last written, already formatted. A raw
    # timestamp is one more thing for a caller to decide how to render,
    # and every caller would decide the same way.
    #

    modified: str

    #
    # How long ago that was, in words. "10 minutes ago" answers the
    # question people actually ask, which is which save is newer.
    #

    age: str

    version: int

    checksum: str

    @property
    def description(self) -> str:
        """
        One line naming the save and when it was written.
        """

        parts = [self.where]

        if self.age:
            parts.append(f"saved {self.age}")

        if self.version:
            parts.append(f"version {self.version}")

        return " · ".join(parts)


def describe_age(moment: datetime | None, now: datetime | None = None) -> str:
    """
    Render how long ago something happened, roughly.

    Deliberately coarse. "3 hours ago" is what someone needs in order
    to recognise a play session; "3 hours 14 minutes" only invites
    reading a precision that the underlying timestamps do not have.
    """

    if moment is None:
        return ""

    reference = now or datetime.now(moment.tzinfo)

    seconds = (reference - moment).total_seconds()

    #
    # Clocks disagree between devices, so a remote save can look like
    # it was written in the future. Saying so is more honest than
    # rendering a negative interval.
    #

    if seconds < -60:
        return "in the future (check the clocks)"

    if seconds < 60:
        return "just now"

    minutes = int(seconds // 60)

    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

    hours = minutes // 60

    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    days = hours // 24

    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"

    months = days // 30

    return f"{months} month{'s' if months != 1 else ''} ago"
