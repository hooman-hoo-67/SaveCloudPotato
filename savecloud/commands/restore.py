"""
Restore a save snapshot.
"""

from __future__ import annotations

import typer

from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService


app = typer.Typer()


@app.callback(invoke_without_command=True)
def restore(
    game_id: str,
    version: int,
) -> None:
    """
    Restore a save snapshot.
    """

    game = RegistryService.load_game(
        game_id,
    )

    SaveService.restore_version(
        game,
        version,
    )

    typer.secho(
        f"✓ Restored snapshot {version}.",
        fg=typer.colors.GREEN,
    )