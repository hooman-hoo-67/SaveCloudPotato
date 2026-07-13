"""
Register a game with SaveCloud.
"""

from enum import Enum

import typer

from savecloud.adapters import AdapterRegistry
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

from savecloud.storage import (
    backend_exists,
    SUPPORTED_BACKENDS,
)


def choose_enum(
    enum_type: type[Enum],
    title: str,
):
    """
    Prompt the user to choose an enum value from a numbered list.
    """

    typer.echo()
    typer.echo(title)

    members = list(enum_type)

    for index, member in enumerate(
        members,
        start=1,
    ):
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

    adapter = (
        prompt_required(
            "Adapter",
        )
        .strip()
        .lower()
    )

    if not AdapterRegistry.exists(adapter):
        typer.secho(
            f'Unsupported adapter: "{adapter}".',
            fg=typer.colors.RED,
        )

        typer.echo("Supported adapters:")

        for name in AdapterRegistry.names():
            typer.echo(f"  - {name}")

        raise typer.Exit(
            code=1,
        )

    adapter_class = AdapterRegistry.get(adapter)

    storage_backend = prompt_required(
        "Storage backend",
    )

    storage_backend = storage_backend.strip().lower()

    if not backend_exists(storage_backend):
        typer.secho(
            f'Unsupported storage backend: "{storage_backend}".',
            fg=typer.colors.RED,
        )

        typer.echo("Supported storage backends:")

        for name in SUPPORTED_BACKENDS:
            typer.echo(f"  - {name}")

        raise typer.Exit(
            code=1,
        )

    identifier = adapter_class.prompt_identifier()

    working_save_path = adapter_class.locate_save(
        identifier,
    )

    if working_save_path is None:
        typer.secho(
            "Unable to locate save directory.",
            fg=typer.colors.RED,
        )

        raise typer.Exit(
            code=1,
        )
        if not adapter_class.validate_save(
            working_save_path,
        ):
            typer.secho(
                f"{adapter_class.display_name()} save directory is invalid.",
                fg=typer.colors.RED,
            )

            raise typer.Exit(
                code=1,
            )

    launch_command = prompt_required(
        "Launch command",
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

    if RegistryService.exists(
        game.manifest.game_id,
    ):
        typer.secho(
            f'Game "{game.manifest.game_id}" is already registered.',
            fg=typer.colors.RED,
        )
        raise typer.Exit(
            code=1,
        )

    RegistryService.create_registry(
        game,
    )

    SaveCloudLibrary.create_game_library(
        game,
    )

    DeviceService.create_profile(
        profile,
    )

    typer.echo()
    typer.echo("✓ Game successfully registered.")
