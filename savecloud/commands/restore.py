"""
Restore a save snapshot.
"""

from __future__ import annotations

import typer

from savecloud.services.save import SaveService
from savecloud.utils.output import require_game


def restore(
    game_id: str,
    version: int,
) -> None:
    """
    Restore a save snapshot.
    """

    game = require_game(game_id)

    try:
        SaveService.restore_version(game, version)

    except FileNotFoundError:
        typer.secho(
            f"✗ Snapshot {version} does not exist.",
            fg=typer.colors.RED,
        )

        available = SaveService.list_versions(game)

        if available:
            typer.echo()
            typer.echo(
                "Available snapshots: "
                + ", ".join(str(number) for number in available)
            )

        raise typer.Exit(code=1)

    typer.secho(
        f"✓ Restored snapshot {version}.",
        fg=typer.colors.GREEN,
    )
