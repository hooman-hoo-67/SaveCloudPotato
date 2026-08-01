"""
Show available save snapshots.
"""

from __future__ import annotations

import typer

from savecloud.services.library import SaveCloudLibrary
from savecloud.services.save import SaveService
from savecloud.utils import output
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

    if output.json_mode():

        output.emit(
            {
                "ok": True,
                "game_id": game.manifest.game_id,
                #
                # Which version is restored, from the library that
                # tracks it. The runtime's field of the same name is
                # written at registration and never advanced, so this
                # reported 0 no matter which version was in place.
                #
                "current_version": SaveCloudLibrary.load_library_metadata(
                    game.manifest.game_id
                ).current_version,
                "versions": versions,
            }
        )

        return

    if not versions:
        typer.echo("No snapshots available.")
        return

    typer.echo("Available snapshots")
    typer.echo("-------------------")

    for version in versions:
        typer.echo(version)
