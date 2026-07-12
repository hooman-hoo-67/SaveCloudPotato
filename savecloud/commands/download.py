"""
Download a managed save from the configured storage backend.
"""

from __future__ import annotations

import typer

from savecloud.services.registry import RegistryService
from savecloud.services.sync import SyncService

app = typer.Typer()


@app.callback(invoke_without_command=True)
def download(
    game_id: str,
) -> None:
    """
    Download a managed save.
    """

    game = RegistryService.load_game(
        game_id,
    )

    SyncService.download(
        game,
    )

    typer.secho(
        "✓ Save downloaded successfully.",
        fg=typer.colors.GREEN,
    )
