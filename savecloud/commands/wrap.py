"""
Run a game supplied by Steam, with synchronization around it.

This is the inverse of `play`. Instead of SaveCloud starting the game,
Steam starts SaveCloud and hands it the command it would otherwise have
run. Put this in a game's Launch Options:

    savecloud wrap <game-id> -- %command%

Steam replaces %command% with the full invocation, including the
Proton runtime for a Windows game. SaveCloud synchronizes, runs it,
waits for it to exit, and captures the save.

The process tree matters: the game is a child of this process, so its
exit is observable. `savecloud play` with the Steam launcher cannot
manage that, which is why it refuses.
"""

from __future__ import annotations

from typing import List, Optional

import typer

from savecloud.services.locking import GameBusyError
from savecloud.services.autosync import AutoSyncService
from savecloud.services.sync import SyncConflictError
from savecloud.utils.output import report_busy, report_conflict, require_game, resolution_from_flags


def wrap(
    game_id: str = typer.Argument(
        ...,
        help="Registered game the command belongs to.",
    ),
    command: Optional[List[str]] = typer.Argument(
        None,
        help="The command to run, after a -- separator.",
    ),
    keep_local: bool = typer.Option(
        False,
        "--keep-local",
        help="Resolve conflicts by keeping this device's save.",
    ),
    keep_remote: bool = typer.Option(
        False,
        "--keep-remote",
        help="Resolve conflicts by keeping the remote save.",
    ),
) -> None:
    """
    Synchronize, run a command supplied by Steam, then capture the save.
    """

    resolution = resolution_from_flags(keep_local, keep_remote)

    argv = list(command or [])

    #
    # Pass-through parsing is enabled so that the game's own options
    # reach the game instead of being read as SaveCloud's. A side
    # effect is that click no longer consumes the "--" separator, so it
    # arrives as a literal argument and has to be dropped here.
    #

    if argv and argv[0] == "--":
        argv = argv[1:]

    #
    # Option parsing stops at the game ID, so SaveCloud's own options
    # only work before it. Placing one after would otherwise be handed
    # to the game as part of its command line and fail obscurely.
    #

    own_options = {"--keep-local", "--keep-remote"}

    if argv and argv[0] in own_options:
        typer.secho(
            f"{argv[0]} must come before the game ID.",
            fg=typer.colors.RED,
        )

        typer.echo()
        typer.echo(f"    savecloud wrap {argv[0]} {game_id} -- %command%")

        raise typer.Exit(code=2)

    if not argv:
        typer.secho(
            "No command was supplied.",
            fg=typer.colors.RED,
        )

        typer.echo()
        typer.echo("Set the game's Steam launch options to:")
        typer.echo()
        typer.echo(f"    savecloud wrap {game_id} -- %command%")

        raise typer.Exit(code=2)

    game = require_game(game_id)

    try:
        result = AutoSyncService.wrap(game, argv, resolution)

    except GameBusyError as error:
        #
        # Another session, or a sync in progress. Starting a second one
        # would have both capture the same working save afterwards.
        #

        report_busy(error)

    except SyncConflictError as error:
        report_conflict(error)

        typer.echo()
        typer.echo("The game was not launched.")

        raise typer.Exit(code=1)

    except FileNotFoundError:
        typer.secho(
            f"Could not run: {argv[0]}",
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=127)

    for warning in result.warnings:
        typer.secho(
            f"! {warning}",
            fg=typer.colors.YELLOW,
        )

    if result.exit_code != 0:
        typer.secho(
            f"! Game exited with code {result.exit_code}. "
            f"The save was not uploaded.",
            fg=typer.colors.YELLOW,
        )

        #
        # Pass the game's exit code through, so Steam reports what
        # actually happened rather than what SaveCloud thought of it.
        #

        raise typer.Exit(code=result.exit_code)

    if result.uploaded:
        typer.secho(
            "✓ Save uploaded.",
            fg=typer.colors.GREEN,
        )
