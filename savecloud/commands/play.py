"""
Launch a managed game with automatic synchronization.
"""

from __future__ import annotations

import typer

from savecloud.services.autosync import AutoSyncService
from savecloud.services.registry import RegistryService

app = typer.Typer()


@app.callback(invoke_without_command=True)
def play(
    game_id: str,
) -> None:
    """
    Launch a managed game using the automatic
    synchronization workflow.
    """

    game = RegistryService.load_game(
        game_id,
    )

    exit_code = AutoSyncService.play(
        game,
    )

    typer.secho(
        f"✓ Game exited successfully (exit code {exit_code}).",
        fg=typer.colors.GREEN,
    )
