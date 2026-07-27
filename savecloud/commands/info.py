"""
Display information about a registered game.
"""

import typer

from savecloud.services.configuration import ConfigurationService
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService


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

    typer.echo(f"Current Version : {game.runtime.current_version}")

    typer.echo()

    typer.echo(f"Last Device     : {game.runtime.last_device}")

    typer.echo(f"Last Sync       : {game.runtime.last_sync}")

    typer.echo(f"Last Launch     : {game.runtime.last_launch}")

    typer.echo(f"Last Exit       : {game.runtime.last_exit}")

    typer.echo(f"Exit Code       : {game.runtime.last_exit_code}")

    typer.echo()

    typer.echo(f"Last Error      : {game.runtime.last_error}")

    typer.echo()

    typer.echo(f"Device          : {profile.device_name}")

    typer.echo(f"Working Save    : {profile.working_save_path}")

    typer.echo(f"Launch Command  : {profile.launch_command}")
    typer.echo(f"Launcher        : {profile.launcher}")
