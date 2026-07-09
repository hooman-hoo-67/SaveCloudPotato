"""
Show available save snapshots.
"""

from __future__ import annotations

import typer

from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService

app = typer.Typer()


@app.callback(invoke_without_command=True)
def history(
    game_id: str,
) -> None:
    """
    Show available save snapshots.
    """

    game = RegistryService.load_game(
        game_id,
    )

    versions = SaveService.list_versions(
        game,
    )

    if not versions:
        typer.echo("No snapshots available.")
        return

    typer.echo("Available snapshots")
    typer.echo("-------------------")

    for version in versions:
        typer.echo(version)
