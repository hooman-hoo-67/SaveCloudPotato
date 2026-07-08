"""
Register a game with SaveCloud.
"""

from pathlib import Path

import typer

from savecloud.models.device_profile import DeviceProfile
from savecloud.models.game import (
    Game,
    GameManifest,
    GameRuntime,
    LaunchType,
    Platform,
)
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService

app = typer.Typer()


@app.command()
def register() -> None:
    """
    Register a game with SaveCloud.
    """

    display_name = typer.prompt("Display name")

    game_id = typer.prompt("Game ID")

    launch_type = LaunchType(
        typer.prompt(
            "Launch type (steam, heroic, lutris, manual)"
        ).lower()
    )

    platform = Platform(
        typer.prompt(
            "Platform (emulator, proton, native)"
        ).lower()
    )

    adapter = typer.prompt("Adapter")

    storage_backend = typer.prompt(
        "Storage backend"
    )

    working_save_path = Path(
        typer.prompt("Working save path")
    )

    launch_command = typer.prompt(
        "Launch command"
    )

    manifest = GameManifest(
        game_id=game_id,
        display_name=display_name,
        launch_type=launch_type,
        platform=platform,
        adapter=adapter,
        storage_backend=storage_backend,
    )

    runtime = GameRuntime()

    game = Game(
        manifest=manifest,
        runtime=runtime,
    )

    profile = DeviceProfile(
        device_id=SaveCloudLibrary.device_id(),
        device_name=SaveCloudLibrary.device_name(),
        game_id=game_id,
        working_save_path=working_save_path,
        launch_command=launch_command,
    )

    if RegistryService.exists(game.manifest.game_id):
        typer.secho(
            f'Game "{game.manifest.game_id}" is already registered.',
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    RegistryService.create_registry(game)
    SaveCloudLibrary.create_game_library(game)
    DeviceService.create_profile(profile)

    typer.echo()
    typer.echo("✓ Game successfully registered.")
