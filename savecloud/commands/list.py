"""
List all registered games.
"""

import typer

from savecloud.services.autosync import auto_sync_enabled
from savecloud.services.registry import RegistryService
from savecloud.utils import output


def list() -> None:
    """
    List all registered games.
    """

    games = RegistryService.list_games()

    if output.json_mode():

        output.emit(
            {
                "ok": True,
                "games": [
                    {
                        "game_id": game.manifest.game_id,
                        "display_name": game.manifest.display_name,
                        "platform": game.manifest.platform.value,
                        "adapter": game.manifest.adapter,
                        "sync_enabled": game.manifest.sync_enabled,
                        "auto_sync": auto_sync_enabled(game),
                        "status": game.runtime.status.value,
                        "pending_upload": game.runtime.pending_upload,
                    }
                    for game in games
                ],
            }
        )

        return

    if not games:
        typer.echo("No games are currently registered.")
        return

    typer.echo("Registered Games")
    typer.echo("----------------")

    for game in games:
        typer.echo(f"{game.manifest.display_name} ({game.manifest.game_id})")
