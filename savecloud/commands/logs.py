"""
Show what SaveCloud has been doing.
"""

from __future__ import annotations

import typer

from savecloud.services import journal
from savecloud.utils import output


def logs(
    lines: int = typer.Option(
        50,
        "--lines",
        "-n",
        help="How many recent lines to show.",
    ),
    path: bool = typer.Option(
        False,
        "--path",
        help="Print the log file's location and exit.",
    ),
) -> None:
    """
    Show recent log entries.
    """

    if path:

        if output.json_mode():
            output.emit({"ok": True, "path": str(journal.path())})

            return

        typer.echo(journal.path())

        return

    recent = journal.recent(lines)

    if output.json_mode():

        output.emit(
            {
                "ok": True,
                "path": str(journal.path()),
                "lines": recent,
            }
        )

        return

    if not recent:
        typer.echo(f"Nothing logged yet. The log lives at {journal.path()}.")

        return

    for line in recent:
        typer.echo(line)
