"""
Synchronize a managed save with its configured storage backend.
"""

from __future__ import annotations

import typer

from savecloud.services.registry import RegistryService
from savecloud.services.sync import SyncService

app = typer.Typer()


@app.callback(invoke_without_command=True)
def sync(
    game_id: str,
) -> None:
    """
    Synchronize a managed save.
    """

    game = RegistryService.load_game(
        game_id,
    )

    SyncService.sync(
        game,
    )

    typer.secho(
        "✓ Synchronization complete.",
        fg=typer.colors.GREEN,
    )
