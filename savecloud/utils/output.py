"""
Shared command helpers.

Commands must never import one another, so anything more than one
command needs lives here. This is presentation, not business logic: it
may call services, but it never implements a workflow.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import typer

from savecloud.models.device_profile import DeviceProfile
from savecloud.models.game import Game
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.sync import ConflictResolution, SyncConflictError
from savecloud.utils import progress


#
# Machine-readable output. Set once by the top-level --json option, and
# read by any command that has a structured form worth emitting.
#
# A flag rather than a separate set of commands: a GUI and a person ask
# the same questions, and two code paths answering them would drift.
#

_json = False


def set_json(enabled: bool) -> None:
    """
    Choose whether commands emit JSON instead of prose.
    """

    global _json

    _json = enabled


def json_mode() -> bool:
    """
    Return whether machine-readable output was requested.
    """

    return _json


def emit(payload: Any) -> None:
    """
    Write a JSON document to stdout.

    One document per command, on stdout alone. Progress and warnings go
    to stderr, so a caller can parse stdout without filtering it.
    """

    typer.echo(json.dumps(payload, indent=2, default=str))


def fail(message: str, **fields: Any) -> None:
    """
    Report a failure in whichever form was asked for, then exit 1.

    Callers get the same exit code either way, so a script can check
    the status without parsing anything.
    """

    if _json:
        emit({"ok": False, "error": message, **fields})

    else:
        typer.secho(f"✗ {message}", fg=typer.colors.RED)

    raise typer.Exit(code=1)


def report_busy(error) -> None:
    """
    Explain that something else is already acting on the game.

    Not an error in the installation, so it says what is happening
    rather than what is broken.
    """

    if _json:
        emit(
            {
                "ok": False,
                "game_id": getattr(error, "game_id", ""),
                "error": str(error),
                "reason": "busy",
            }
        )

    else:
        typer.secho(f"✗ {error}", fg=typer.colors.RED)

        typer.echo()
        typer.echo(
            "Wait for it to finish, or close the game if it is running."
        )

    raise typer.Exit(code=1)


def require_game(game_id: str) -> Game:
    """
    Load a registered game, or exit with a readable message.

    Loading an unregistered game raises straight out of the service
    layer, which reaches the user as a traceback. Every command that
    takes a game ID goes through here instead.
    """

    if not RegistryService.exists(game_id):
        typer.secho(
            f'Game "{game_id}" is not registered.',
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    return RegistryService.load_game(game_id)


def require_profile(game_id: str) -> DeviceProfile:
    """
    Load this device's profile for a game, or exit with guidance.

    A game can be registered and synchronized without being set up on
    this particular machine, which is exactly what `pair` is for.
    """

    device_id = SaveCloudLibrary.device_id()

    if not DeviceService.exists(device_id, game_id):
        typer.secho(
            f'"{game_id}" is not set up on this device.',
            fg=typer.colors.RED,
        )

        typer.echo()
        typer.echo(f"Adopt it here with:  savecloud pair {game_id}")

        raise typer.Exit(code=1)

    return DeviceService.load_profile(device_id, game_id)


def resolution_from_flags(
    keep_local: bool,
    keep_remote: bool,
) -> ConflictResolution:
    """
    Translate command-line flags into a conflict resolution.
    """

    if keep_local and keep_remote:
        typer.secho(
            "Choose either --keep-local or --keep-remote, not both.",
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=2)

    if keep_local:
        return ConflictResolution.LOCAL

    if keep_remote:
        return ConflictResolution.REMOTE

    return ConflictResolution.ABORT


def report_conflict(
    error: SyncConflictError,
) -> None:
    """
    Explain a conflict, describe both saves, and say how to resolve it.

    The description is the point. Being told two saves differ does not
    help anyone choose between them; being told one was written ten
    minutes ago here and the other two hours ago on a Steam Deck does.
    """

    if _json:
        emit(
            {
                "ok": False,
                "game_id": error.game_id,
                "action": "conflict",
                "error": str(error),
                "resolutions": ["keep-local", "keep-remote"],
                "local": _summary_dict(error.local),
                "remote": _summary_dict(error.remote),
            }
        )

        return

    typer.secho(
        f"✗ {error}",
        fg=typer.colors.RED,
    )

    if error.local is not None or error.remote is not None:

        typer.echo()

        for label, summary in (
            ("keep-local ", error.local),
            ("keep-remote", error.remote),
        ):
            if summary is None:
                continue

            typer.echo(f"  {label}   {summary.description}")

    typer.echo()
    typer.echo("Nothing has been overwritten. Resolve it with one of:")
    typer.echo()
    typer.echo(f"  savecloud sync {error.game_id} --keep-local")
    typer.echo(f"  savecloud sync {error.game_id} --keep-remote")
    typer.echo()
    typer.echo("Whichever save loses is kept in this game's version history.")


def _summary_dict(summary) -> dict | None:
    """
    Render a save summary for machine-readable output.
    """

    if summary is None:
        return None

    return {
        "where": summary.where,
        "modified": summary.modified,
        "age": summary.age,
        "version": summary.version,
        "checksum": summary.checksum,
    }


def show_progress(quiet: bool = False) -> None:
    """
    Display progress from long-running backend operations.

    A cloud backend spends a network round trip per file, so an
    otherwise silent minute looks exactly like a hang. On a terminal
    the line is rewritten in place; when redirected, nothing is printed
    rather than filling a log with partial lines.
    """

    if quiet or _json or not sys.stderr.isatty():
        progress.set_reporter(None)
        return

    state = {"width": 0}

    def render(message: str) -> None:

        #
        # Truncate rather than wrap, so a long path does not turn one
        # line of progress into several.
        #

        text = message[:78]

        sys.stderr.write("\r" + text.ljust(state["width"]))
        sys.stderr.flush()

        state["width"] = max(state["width"], len(text))

    progress.set_reporter(render)


def clear_progress() -> None:
    """
    Remove the progress line before printing a result.
    """

    if progress.reporter() is not None and sys.stderr.isatty():
        sys.stderr.write("\r" + " " * 79 + "\r")
        sys.stderr.flush()

    progress.set_reporter(None)
