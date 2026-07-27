"""
Create a snapshot of the current managed save.
"""

from __future__ import annotations

import typer

from savecloud.services.library import SaveCloudLibrary
from savecloud.services.save import SaveService
from savecloud.utils.output import require_game


def snapshot(
    game_id: str,
) -> None:
    """
    Create a snapshot of the current managed save.
    """

    game = require_game(game_id)

    SaveService.create_version(
        game,
    )

    metadata = SaveCloudLibrary.load_library_metadata(
        game_id,
    )

    typer.secho(
        ("✓ Snapshot " f"{metadata.latest_version} created."),
        fg=typer.colors.GREEN,
    )
