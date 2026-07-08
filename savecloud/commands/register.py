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

from enum import Enum


def choose_enum(enum_type: type[Enum], title: str):
    """
    Prompt the user to choose an enum value from a numbered list.
    """

    typer.echo()
    typer.echo(title)

    members = list(enum_type)

    for index, member in enumerate(members, start=1):
        typer.echo(f"{index}. {member.value}")

    while True:
        choice = typer.prompt(
            "Choice",
            type=int,
        )

        if 1 <= choice <= len(members):
            return members[choice - 1]

        typer.secho(
            "Invalid selection. Try again.",
            fg=typer.colors.RED,
        )


def prompt_required(text: str) -> str:
    """
    Prompt until a non-empty value is entered.
    """

    while True:
        value = typer.prompt(text).strip()

        if value:
            return value

        typer.secho(
            "Value cannot be empty.",
            fg=typer.colors.RED,
        )


app = typer.Typer(
    invoke_without_command=True,
)


@app.callback()
def register() -> None:
    """
    Register a game with SaveCloud.
    """

    display_name = prompt_required("Display name")

    game_id = prompt_required("Game ID")

    launch_type = choose_enum(
        LaunchType,
        "Select launch type",
    )

    platform = choose_enum(
        Platform,
        "Select platform",
    )

    adapter = prompt_required("Adapter")

    storage_backend = prompt_required("Storage backend")

    working_save_path = Path(prompt_required("Working save path"))

    launch_command = prompt_required("Launch command")

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
