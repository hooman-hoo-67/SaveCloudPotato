"""
Synchronize managed saves with the configured storage backend.
"""

from __future__ import annotations

import typer

from savecloud.services.registry import RegistryService
from savecloud.services.sync import (
    ConflictResolution,
    StorageUnavailableError,
    SyncAction,
    SyncConflictError,
    SyncService,
)
from savecloud.utils.output import report_conflict, resolution_from_flags


def sync(
    game_id: str = typer.Argument(
        None,
        help="Game to synchronize. Omit to synchronize every game.",
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
    check: bool = typer.Option(
        False,
        "--check",
        help="Report what would happen without changing anything.",
    ),
) -> None:
    """
    Synchronize a managed save.
    """

    resolution = resolution_from_flags(keep_local, keep_remote)

    if game_id is None:
        sync_all(resolution, check)
        return

    if not RegistryService.exists(game_id):
        typer.secho(
            f'Game "{game_id}" is not registered.',
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    game = RegistryService.load_game(game_id)

    try:
        if check:
            typer.echo(f"{game_id}: {SyncService.status(game).value}")
            return

        action = SyncService.sync(game, resolution)

    except SyncConflictError as error:
        report_conflict(error)

        raise typer.Exit(code=1)

    except StorageUnavailableError as error:
        typer.secho(
            f"✗ {error}",
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    messages = {
        SyncAction.UPLOAD: "✓ Uploaded local save.",
        SyncAction.DOWNLOAD: "✓ Downloaded remote save.",
        SyncAction.UP_TO_DATE: "✓ Already up to date.",
    }

    typer.secho(
        messages.get(action, "✓ Synchronization complete."),
        fg=typer.colors.GREEN,
    )


def sync_all(
    resolution: ConflictResolution,
    check: bool,
) -> None:
    """
    Synchronize every registered game.
    """

    games = RegistryService.list_games()

    if not games:
        typer.echo("No games are currently registered.")
        return

    if check:
        for game in games:

            try:
                action = SyncService.status(game)

                typer.echo(f"{game.manifest.game_id}: {action.value}")

            except Exception as error:
                typer.secho(
                    f"{game.manifest.game_id}: {error}",
                    fg=typer.colors.RED,
                )

        return

    results = SyncService.sync_all(resolution)

    if not results:
        typer.echo("No games have synchronization enabled.")
        return

    failures = 0

    for game_id, outcome in results.items():

        if isinstance(outcome, SyncAction):
            typer.echo(f"{game_id}: {outcome.value}")

        else:
            failures += 1

            typer.secho(
                f"{game_id}: {outcome}",
                fg=typer.colors.RED,
            )

    typer.echo()

    if failures:
        typer.secho(
            f"✗ {failures} of {len(results)} games failed to synchronize.",
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    typer.secho(
        f"✓ Synchronized {len(results)} games.",
        fg=typer.colors.GREEN,
    )
