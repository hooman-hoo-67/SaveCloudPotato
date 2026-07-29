"""
Display information about a registered game.
"""

import typer

from savecloud.services.configuration import ConfigurationService
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.library import SaveCloudLibrary as _Library
from savecloud.utils import output


def info(game_id: str) -> None:
    """
    Display information about a registered game.
    """

    if not RegistryService.exists(game_id):

        output.fail(
            f'Game "{game_id}" is not registered.',
            game_id=game_id,
        )

    game = RegistryService.load_game(game_id)

    #
    # A game can be registered and synchronized without being set up
    # here - that is exactly the state `pair` resolves - so a missing
    # profile is reported rather than raised.
    #

    device_id = SaveCloudLibrary.device_id()

    profile = (
        DeviceService.load_profile(device_id, game_id)
        if DeviceService.exists(device_id, game_id)
        else None
    )

    if output.json_mode():

        config = ConfigurationService.load()

        output.emit(
            {
                "ok": True,
                "game": {
                    "game_id": game.manifest.game_id,
                    "display_name": game.manifest.display_name,
                    "launch_type": game.manifest.launch_type.value,
                    "platform": game.manifest.platform.value,
                    "adapter": game.manifest.adapter,
                    "sync_enabled": game.manifest.sync_enabled,
                    "backup_enabled": game.manifest.backup_enabled,
                },
                "storage": {
                    "backend": config.storage_backend,
                    "root": str(config.storage_root),
                    "version_retention": config.version_retention,
                },
                "runtime": {
                    "status": game.runtime.status.value,
                    "pending_upload": game.runtime.pending_upload,
                    "latest_version": SaveCloudLibrary.load_library_metadata(
                        game_id
                    ).latest_version,
                    "restored_from": SaveCloudLibrary.load_library_metadata(
                        game_id
                    ).current_version,
                    "last_device": game.runtime.last_device,
                    "last_sync": game.runtime.last_sync,
                    "last_launch": game.runtime.last_launch,
                    "last_exit": game.runtime.last_exit,
                    "last_exit_code": game.runtime.last_exit_code,
                    "last_error": game.runtime.last_error,
                    "last_sync_checksum": game.runtime.last_sync_checksum,
                },
                "device": None
                if profile is None
                else {
                    "device_id": profile.device_id,
                    "device_name": profile.device_name,
                    "working_save_path": str(profile.working_save_path),
                    "launch_command": profile.launch_command,
                    "launcher": profile.launcher,
                    "auto_sync": profile.enabled,
                },
            }
        )

        return

    typer.echo("Game Information")
    typer.echo("----------------")
    typer.echo()

    typer.echo(f"Display Name    : {game.manifest.display_name}")

    typer.echo(f"Game ID         : {game.manifest.game_id}")

    typer.echo()

    typer.echo(f"Launch Type     : {game.manifest.launch_type.value}")

    typer.echo(f"Platform        : {game.manifest.platform.value}")

    typer.echo(f"Adapter         : {game.manifest.adapter}")

    typer.echo(f"Sync Enabled    : {game.manifest.sync_enabled}")

    typer.echo(f"Backup Enabled  : {game.manifest.backup_enabled}")

    typer.echo()

    #
    # Storage is an installation-wide setting, not a per-game one.
    #

    config = ConfigurationService.load()

    typer.echo(f"Storage Backend : {config.storage_backend} (installation-wide)")

    typer.echo(f"Storage Root    : {config.storage_root}")

    typer.echo()

    typer.echo("Runtime")
    typer.echo("-------")
    typer.echo()

    typer.echo(f"Status          : {game.runtime.status.value}")

    typer.echo(f"Pending Upload  : {game.runtime.pending_upload}")

    #
    # From the library, which owns save data. The runtime's copy of
    # this is written at registration and never updated.
    #

    metadata = _Library.load_library_metadata(game_id)

    typer.echo(f"Latest Version  : {metadata.latest_version}")

    if metadata.current_version:
        typer.echo(f"Restored From   : version {metadata.current_version}")

    typer.echo()

    typer.echo(f"Last Device     : {game.runtime.last_device}")

    typer.echo(f"Last Sync       : {game.runtime.last_sync}")

    typer.echo(f"Last Launch     : {game.runtime.last_launch}")

    typer.echo(f"Last Exit       : {game.runtime.last_exit}")

    typer.echo(f"Exit Code       : {game.runtime.last_exit_code}")

    typer.echo()

    typer.echo(f"Last Error      : {game.runtime.last_error}")

    typer.echo()

    if profile is None:
        typer.secho(
            "This game is not set up on this device.",
            fg=typer.colors.YELLOW,
        )

        typer.echo(f"Adopt it here with:  savecloud pair {game_id}")

        return

    typer.echo(f"Device          : {profile.device_name}")

    typer.echo(f"Working Save    : {profile.working_save_path}")

    typer.echo(f"Launch Command  : {profile.launch_command}")
    typer.echo(f"Launcher        : {profile.launcher}")

    typer.echo(f"Automatic Sync  : {'on' if profile.enabled else 'off'}")
