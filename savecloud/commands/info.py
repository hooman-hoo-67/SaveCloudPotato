"""
Display information about a registered game.
"""

import typer

from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService

app = typer.Typer()


@app.command()
def info(game_id: str) -> None:
    """
    Display information about a registered game.
    """

    if not RegistryService.exists(game_id):
        typer.secho(
            f'Game "{game_id}" is not registered.',
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    game = RegistryService.load_game(game_id)

    profile = DeviceService.load_profile(
        SaveCloudLibrary.device_id(),
        game_id,
    )

    typer.echo("Game Information")
    typer.echo("----------------")
    typer.echo()

    typer.echo(
        f"Display Name    : {game.manifest.display_name}"
    )

    typer.echo(
        f"Game ID         : {game.manifest.game_id}"
    )

    typer.echo()

    typer.echo(
        f"Launch Type     : {game.manifest.launch_type.value}"
    )

    typer.echo(
        f"Platform        : {game.manifest.platform.value}"
    )

    typer.echo(
        f"Adapter         : {game.manifest.adapter}"
    )

    typer.echo()

    typer.echo(
        f"Storage Backend : {game.manifest.storage_backend}"
    )

    typer.echo()

    typer.echo(
        f"Device          : {profile.device_name}"
    )

    typer.echo(
        f"Working Save    : {profile.working_save_path}"
    )

    typer.echo(
        f"Launch Command  : {profile.launch_command}"
    )