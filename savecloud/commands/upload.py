"""
Upload a managed save, overwriting whatever storage holds.
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


def upload(
    game_id: str,
) -> None:
    """
    Upload a managed save, overwriting whatever storage holds.
    """

    game = require_game(game_id)

    show_progress()

    try:
        SyncService.upload(game)

    except GameBusyError as error:
        clear_progress()

        report_busy(error)

    except StorageUnavailableError as error:
        clear_progress()

        typer.secho(f"✗ {error}", fg=typer.colors.RED)

        raise typer.Exit(code=1)

    clear_progress()

    typer.secho(
        "✓ Save uploaded successfully.",
        fg=typer.colors.GREEN,
    )
