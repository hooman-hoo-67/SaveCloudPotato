"""
Create a snapshot of the current managed save.
"""

from __future__ import annotations

import typer

from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService


app = typer.Typer()


@app.callback(invoke_without_command=True)
def snapshot(
    game_id: str,
) -> None:
    """
    Create a snapshot of the current managed save.
    """

    game = RegistryService.load_game(
        game_id,
    )

    SaveService.create_version(
        game,
    )

    metadata = SaveCloudLibrary.load_library_metadata(
        game_id,
    )

    typer.secho(
        (
            "✓ Snapshot "
            f"{metadata.latest_version} created."
        ),
        fg=typer.colors.GREEN,
    )