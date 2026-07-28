"""
Download a managed save, overwriting whatever this device holds.
"""

from __future__ import annotations

import typer

from savecloud.services.sync import StorageUnavailableError, SyncService
from savecloud.utils.output import require_game


def download(
    game_id: str,
) -> None:
    """
    Download a managed save, overwriting whatever this device holds.
    """

    game = require_game(game_id)

    try:
        SyncService.download(game)

    except StorageUnavailableError as error:
        typer.secho(f"✗ {error}", fg=typer.colors.RED)

        raise typer.Exit(code=1)

    typer.secho(
        "✓ Save downloaded successfully.",
        fg=typer.colors.GREEN,
    )
