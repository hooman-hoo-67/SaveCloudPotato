"""
Export a managed save from the SaveCloud library.
"""

from __future__ import annotations

import typer

from savecloud.services.library import SaveCloudLibrary
from savecloud.services.save import SaveService
from savecloud.utils.output import require_game, require_profile


def export_save(
    game_id: str,
) -> None:
    """
    Export the managed save to the working save directory.
    """

    game = require_game(game_id)

    profile = require_profile(game_id)

    try:
        SaveService.export_save(game, profile)

    except (FileNotFoundError, NotADirectoryError) as error:
        typer.secho(f"✗ {error}", fg=typer.colors.RED)

        raise typer.Exit(code=1)

    SaveCloudLibrary.mark_export(game_id)

    typer.secho(
        "✓ Save exported successfully.",
        fg=typer.colors.GREEN,
    )
