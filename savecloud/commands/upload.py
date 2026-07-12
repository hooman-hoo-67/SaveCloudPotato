"""
Upload a managed save to the configured storage backend.
"""

from __future__ import annotations

import typer

from savecloud.services.registry import RegistryService
from savecloud.services.sync import SyncService

app = typer.Typer()


@app.callback(invoke_without_command=True)
def upload(
    game_id: str,
) -> None:
    """
    Upload a managed save.
    """

    game = RegistryService.load_game(
        game_id,
    )

    SyncService.upload(
        game,
    )

    typer.secho(
        "✓ Save uploaded successfully.",
        fg=typer.colors.GREEN,
    )
