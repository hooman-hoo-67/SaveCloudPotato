"""
Adopt games that already exist in storage onto this device.

Pairing is what makes a second device cheap: the registry and library
travel through the storage backend, so only the device-specific
details - where the save lives here, and how the game starts here -
need to be supplied locally.
"""

from __future__ import annotations

import typer

from savecloud.adapters import AdapterRegistry
from savecloud.launchers import LauncherRegistry
from savecloud.models.device_profile import DeviceProfile
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService
from savecloud.services.sync import StorageUnavailableError, SyncService
from savecloud.utils.prompt import choose_option, prompt_required

def list_remote(remote: list[str]) -> None:
    """
    Report which games storage holds and their state here.
    """

    if not remote:
        typer.echo("Storage holds no games.")
        return

    device_id = SaveCloudLibrary.device_id()

    typer.echo("Games in storage")
    typer.echo("----------------")
    typer.echo()

    for game_id in remote:

        if DeviceService.exists(device_id, game_id):
            status = "paired"

        elif RegistryService.exists(game_id):
            status = "registered, not set up on this device"

        else:
            status = "available"

        typer.echo(f"{game_id:<30} {status}")


def pair(
    game_id: str = typer.Argument(
        None,
        help="Game to adopt onto this device.",
    ),
    show_list: bool = typer.Option(
        False,
        "--list",
        help="List games available in storage without pairing any.",
    ),
) -> None:
    """
    Adopt a game from storage onto this device.
    """

    try:
        remote = SyncService.remote_games()

    except StorageUnavailableError as error:
        typer.secho(f"✗ {error}", fg=typer.colors.RED)

        raise typer.Exit(code=1)

    if show_list:
        list_remote(remote)
        raise typer.Exit()

    if not remote:
        typer.echo("Storage holds no games to pair.")
        raise typer.Exit()

    device_id = SaveCloudLibrary.device_id()

    if game_id is None:

        available = [
            candidate
            for candidate in remote
            if not DeviceService.exists(device_id, candidate)
        ]

        if not available:
            typer.echo("Every game in storage is already paired with this device.")
            raise typer.Exit()

        game_id = choose_option(available, "Select a game to pair")

    if game_id not in remote:
        typer.secho(
            f'Storage holds no game called "{game_id}".',
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    if DeviceService.exists(device_id, game_id):
        typer.secho(
            f'"{game_id}" is already paired with this device.',
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    #
    # Pull the registry and library down first, so the manifest can
    # tell us which adapter this game uses.
    #

    typer.echo(f"Downloading {game_id}...")

    try:
        game = SyncService.adopt(game_id)

    except (FileNotFoundError, StorageUnavailableError) as error:
        typer.secho(f"✗ {error}", fg=typer.colors.RED)

        raise typer.Exit(code=1)

    typer.secho(
        f"✓ Adopted {game.manifest.display_name}.",
        fg=typer.colors.GREEN,
    )

    #
    # Everything from here is device-specific and cannot be
    # synchronized.
    #

    adapter_class = AdapterRegistry.get(game.manifest.adapter)

    if adapter_class is None:
        typer.secho(
            f'Unknown adapter: "{game.manifest.adapter}".',
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    typer.echo()
    typer.echo(f"Where does {game.manifest.display_name} keep its save on this device?")

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

    launch_command = prompt_required("Launch command")

    profile = DeviceProfile(
        device_id=device_id,
        device_name=SaveCloudLibrary.device_name(),
        game_id=game_id,
        working_save_path=working_save_path,
        launch_command=launch_command,
        launcher=selected_launcher,
    )

    DeviceService.create_profile(profile)

    #
    # Publish the downloaded save into the working save directory so
    # the game is immediately playable.
    #

    SaveService.export_save(game, profile)

    SaveCloudLibrary.mark_export(game_id)

    typer.echo()
    typer.secho(
        f"✓ {game.manifest.display_name} is ready to play on this device.",
        fg=typer.colors.GREEN,
    )
