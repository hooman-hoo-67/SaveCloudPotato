"""
Launch a managed game with automatic synchronization.
"""

from __future__ import annotations

import typer

from savecloud.services.locking import GameBusyError
from savecloud.services.autosync import AutoSyncService, UntrackableLaunchError
from savecloud.services.registry import RegistryService
from savecloud.services.sync import SyncConflictError
from savecloud.utils.output import report_busy, report_conflict, resolution_from_flags


def play(
    game_id: str,
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
    Launch a managed game using the automatic
    synchronization workflow.
    """

    resolution = resolution_from_flags(keep_local, keep_remote)

    if not RegistryService.exists(game_id):
        typer.secho(
            f'Game "{game_id}" is not registered.',
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    game = RegistryService.load_game(game_id)

    try:
        result = AutoSyncService.play(game, resolution)

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

    except UntrackableLaunchError as error:
        typer.secho(
            f"✗ {error}",
            fg=typer.colors.RED,
        )

        typer.echo()
        typer.echo(
            "Let Steam start SaveCloud instead. Put this in the game's "
            "Steam launch options:"
        )
        typer.echo()
        typer.echo(f"    savecloud wrap {game_id} -- %command%")
        typer.echo()
        typer.echo("Then launch the game from Steam as usual.")

        raise typer.Exit(code=1)

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

        raise typer.Exit(code=result.exit_code)

    if result.uploaded:
        typer.secho(
            "✓ Game exited cleanly and the save was uploaded.",
            fg=typer.colors.GREEN,
        )

        return

    typer.secho(
        "✓ Game exited cleanly.",
        fg=typer.colors.GREEN,
    )
