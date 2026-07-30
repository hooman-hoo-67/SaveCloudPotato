"""
Download a managed save, overwriting whatever this device holds.
"""

from __future__ import annotations

import typer

from savecloud.services.locking import GameBusyError
from savecloud.services.sync import StorageUnavailableError, SyncService
from savecloud.utils.output import (
    clear_progress,
    report_busy,
    require_game,
    show_progress,
)


def download(
    game_id: str,
) -> None:
    """
    Download a managed save, overwriting whatever this device holds.
    """

    game = require_game(game_id)

    show_progress()

    try:
        SyncService.download(game)

    except GameBusyError as error:
        clear_progress()

        report_busy(error)

    except StorageUnavailableError as error:
        clear_progress()

        typer.secho(f"✗ {error}", fg=typer.colors.RED)

        raise typer.Exit(code=1)

    clear_progress()

    typer.secho(
        "✓ Save downloaded successfully.",
        fg=typer.colors.GREEN,
    )
