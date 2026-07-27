"""
Import a game's working save into the SaveCloud library.
"""

from __future__ import annotations

import typer

from savecloud.services.library import SaveCloudLibrary
from savecloud.services.save import SaveService
from savecloud.utils.output import require_game, require_profile


def import_save(
    game_id: str,
) -> None:
    """
    Import the current working save into the SaveCloud library.
    """

    game = require_game(game_id)

    profile = require_profile(game_id)

    try:
        SaveService.import_save(game, profile)

    except (FileNotFoundError, NotADirectoryError) as error:
        typer.secho(f"✗ {error}", fg=typer.colors.RED)

        raise typer.Exit(code=1)

    SaveCloudLibrary.mark_import(game_id)

    typer.secho(
        "✓ Save imported successfully.",
        fg=typer.colors.GREEN,
    )
