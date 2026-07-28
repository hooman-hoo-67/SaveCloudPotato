"""
Upload a managed save, overwriting whatever storage holds.
"""

from __future__ import annotations

import typer

from savecloud.services.sync import StorageUnavailableError, SyncService
from savecloud.utils.output import require_game


def upload(
    game_id: str,
) -> None:
    """
    Upload a managed save, overwriting whatever storage holds.
    """

    game = require_game(game_id)

    try:
        SyncService.upload(game)

    except StorageUnavailableError as error:
        typer.secho(f"✗ {error}", fg=typer.colors.RED)

        raise typer.Exit(code=1)

    typer.secho(
        "✓ Save uploaded successfully.",
        fg=typer.colors.GREEN,
    )
