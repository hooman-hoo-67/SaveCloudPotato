"""
Synchronize managed saves with the configured storage backend.
"""

from __future__ import annotations

import typer

from savecloud.services.registry import RegistryService
from savecloud.services.locking import GameBusyError
from savecloud.services.sync import (
    ConflictResolution,
    StorageUnavailableError,
    SyncAction,
    SyncConflictError,
    SyncService,
)
from savecloud.utils import output
from savecloud.utils.output import (
    clear_progress,
    report_busy,
    report_conflict,
    resolution_from_flags,
    show_progress,
)


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

        output.fail(
            f'Game "{game_id}" is not registered.',
            game_id=game_id,
        )

    game = RegistryService.load_game(game_id)

    show_progress()

    try:
        if check:
            action = SyncService.status(game)

            clear_progress()

            if output.json_mode():
                output.emit(
                    {
                        "ok": True,
                        "game_id": game_id,
                        "action": action.value,
                        "applied": False,
                    }
                )

                return

            typer.echo(f"{game_id}: {action.value}")

            return

        action = SyncService.sync(game, resolution)

    except SyncConflictError as error:
        clear_progress()

        report_conflict(error)

        raise typer.Exit(code=1)

    except GameBusyError as error:
        clear_progress()

        report_busy(error)

    except StorageUnavailableError as error:
        clear_progress()

        output.fail(str(error), game_id=game_id, reason="storage-unavailable")

    clear_progress()

    if output.json_mode():
        output.emit(
            {
                "ok": True,
                "game_id": game_id,
                "action": action.value,
                "applied": True,
            }
        )

        return

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

        if output.json_mode():
            output.emit({"ok": True, "games": []})

            return

        typer.echo("No games are currently registered.")
        return

    if check:

        checked = []

        for game in games:

            try:
                action = SyncService.status(game)

                checked.append(
                    {
                        "game_id": game.manifest.game_id,
                        "action": action.value,
                    }
                )

                if not output.json_mode():
                    typer.echo(f"{game.manifest.game_id}: {action.value}")

            except Exception as error:

                checked.append(
                    {
                        "game_id": game.manifest.game_id,
                        "error": str(error),
                    }
                )

                if not output.json_mode():
                    typer.secho(
                        f"{game.manifest.game_id}: {error}",
                        fg=typer.colors.RED,
                    )

        if output.json_mode():
            output.emit({"ok": True, "applied": False, "games": checked})

        return

    show_progress()

    results = SyncService.sync_all(resolution)

    clear_progress()

    if not results:

        if output.json_mode():
            output.emit({"ok": True, "applied": True, "games": []})

            return

        typer.echo("No games have synchronization enabled.")
        return

    failures = 0

    synced = []

    for game_id, outcome in results.items():

        if isinstance(outcome, SyncAction):

            synced.append({"game_id": game_id, "action": outcome.value})

            if not output.json_mode():
                typer.echo(f"{game_id}: {outcome.value}")

        else:
            failures += 1

            synced.append({"game_id": game_id, "error": str(outcome)})

            if not output.json_mode():
                typer.secho(
                    f"{game_id}: {outcome}",
                    fg=typer.colors.RED,
                )

    if output.json_mode():

        output.emit(
            {
                "ok": failures == 0,
                "applied": True,
                "failures": failures,
                "games": synced,
            }
        )

        if failures:
            raise typer.Exit(code=1)

        return

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
