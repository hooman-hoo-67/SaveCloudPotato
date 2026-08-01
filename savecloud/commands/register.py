"""
Register a game with SaveCloud.
"""

import typer

from savecloud.adapters import AdapterRegistry
from savecloud.launchers import LauncherRegistry
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
from savecloud.utils.identifiers import InvalidGameIdError, validate_game_id
from savecloud.utils.prompt import choose_enum, choose_option, prompt_required


def register() -> None:
    """
    Register a game with SaveCloud.
    """

    display_name = prompt_required("Display name")

    game_id = prompt_required("Game ID")

    #
    # Before anything else is asked. An ID names a folder, and finding
    # that out after choosing an adapter and locating a save directory
    # would throw away everything already typed.
    #

    try:
        validate_game_id(game_id)

    except InvalidGameIdError as error:
        typer.secho(str(error), fg=typer.colors.RED)

        raise typer.Exit(code=1)

    #
    # Fail before asking anything else if the game already exists.
    #

    if RegistryService.exists(game_id):
        typer.secho(
            f'Game "{game_id}" is already registered.',
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    launch_type = choose_enum(
        LaunchType,
        "Select launch type",
    )

    platform = choose_enum(
        Platform,
        "Select platform",
    )

    adapter = choose_option(
        AdapterRegistry.names(),
        "Select adapter",
    )

    adapter_class = AdapterRegistry.get(adapter)

    assert adapter_class is not None

    identifier = adapter_class.prompt_identifier()

    working_save_path = adapter_class.locate_save(identifier)

    if working_save_path is None:
        typer.secho(
            "Unable to locate save directory.",
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    if not adapter_class.validate_save(working_save_path):
        typer.secho(
            f"{adapter_class.display_name()} save directory is invalid.",
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    selected_launcher = choose_option(
        LauncherRegistry.names(),
        "Select launcher",
    )

    #
    # Optional. A game launched from Steam is started by Steam, which
    # hands SaveCloud the real command through `wrap`.
    #

    launch_command = typer.prompt(
        "Launch command (optional, only needed for `savecloud play`)",
        default="",
        show_default=False,
    ).strip()

    manifest = GameManifest(
        game_id=game_id,
        display_name=display_name,
        launch_type=launch_type,
        platform=platform,
        adapter=adapter,
    )

    game = Game(
        manifest=manifest,
        runtime=GameRuntime(),
    )

    profile = DeviceProfile(
        device_id=SaveCloudLibrary.device_id(),
        device_name=SaveCloudLibrary.device_name(),
        game_id=game_id,
        working_save_path=working_save_path,
        launch_command=launch_command,
        launcher=selected_launcher,
    )

    RegistryService.create_registry(game)

    SaveCloudLibrary.create_game_library(game)

    DeviceService.create_profile(profile)

    typer.echo()
    typer.echo("✓ Game successfully registered.")
