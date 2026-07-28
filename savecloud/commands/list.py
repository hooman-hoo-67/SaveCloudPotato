"""
List all registered games.
"""

import typer

from savecloud.services.registry import RegistryService


def list() -> None:
    """
    List all registered games.
    """

    games = RegistryService.list_games()

    if not games:
        typer.echo("No games are currently registered.")
        return

    typer.echo("Registered Games")
    typer.echo("----------------")

    for game in games:
        typer.echo(f"{game.manifest.display_name} ({game.manifest.game_id})")
