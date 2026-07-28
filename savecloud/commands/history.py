"""
Show available save snapshots.
"""

from __future__ import annotations

import typer

from savecloud.services.save import SaveService
from savecloud.utils.output import require_game


def history(
    game_id: str,
) -> None:
    """
    Show available save snapshots.
    """

    game = require_game(game_id)

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
