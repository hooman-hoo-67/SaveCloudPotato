"""
Unregister a game from SaveCloud.
"""

import typer

from savecloud.services.registry import RegistryService
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary

app = typer.Typer()


@app.command()
def unregister(game_id: str) -> None:
    """
    Unregister a game from SaveCloud.
    """

    if not RegistryService.exists(game_id):
        typer.secho(
            f'Game "{game_id}" is not registered.',
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    confirmed = typer.confirm(
        f'Unregister "{game_id}"?'
    )

    if not confirmed:
        typer.echo("Operation cancelled.")
        raise typer.Exit()

    DeviceService.delete_profile(
        SaveCloudLibrary.device_id(),
        game_id,
    )

    RegistryService.delete_registry(game_id)

    SaveCloudLibrary.delete_game_library(game_id)

    typer.echo()
    typer.echo("✓ Game successfully unregistered.")