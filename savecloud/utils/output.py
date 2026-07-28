"""
Shared command helpers.

Commands must never import one another, so anything more than one
command needs lives here. This is presentation, not business logic: it
may call services, but it never implements a workflow.
"""

from __future__ import annotations

import typer

from savecloud.models.device_profile import DeviceProfile
from savecloud.models.game import Game
from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.sync import ConflictResolution, SyncConflictError


def require_game(game_id: str) -> Game:
    """
    Load a registered game, or exit with a readable message.

    Loading an unregistered game raises straight out of the service
    layer, which reaches the user as a traceback. Every command that
    takes a game ID goes through here instead.
    """

    if not RegistryService.exists(game_id):
        typer.secho(
            f'Game "{game_id}" is not registered.',
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    return RegistryService.load_game(game_id)


def require_profile(game_id: str) -> DeviceProfile:
    """
    Load this device's profile for a game, or exit with guidance.

    A game can be registered and synchronized without being set up on
    this particular machine, which is exactly what `pair` is for.
    """

    device_id = SaveCloudLibrary.device_id()

    if not DeviceService.exists(device_id, game_id):
        typer.secho(
            f'"{game_id}" is not set up on this device.',
            fg=typer.colors.RED,
        )

        typer.echo()
        typer.echo(f"Adopt it here with:  savecloud pair {game_id}")

        raise typer.Exit(code=1)

    return DeviceService.load_profile(device_id, game_id)


def resolution_from_flags(
    keep_local: bool,
    keep_remote: bool,
) -> ConflictResolution:
    """
    Translate command-line flags into a conflict resolution.
    """

    if keep_local and keep_remote:
        typer.secho(
            "Choose either --keep-local or --keep-remote, not both.",
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=2)

    if keep_local:
        return ConflictResolution.LOCAL

    if keep_remote:
        return ConflictResolution.REMOTE

    return ConflictResolution.ABORT


def report_conflict(
    error: SyncConflictError,
) -> None:
    """
    Explain a conflict and how to resolve it.
    """

    typer.secho(
        f"✗ {error}",
        fg=typer.colors.RED,
    )

    typer.echo()
    typer.echo("Nothing has been overwritten. Resolve it with one of:")
    typer.echo()
    typer.echo(f"  savecloud sync {error.game_id} --keep-local")
    typer.echo(f"  savecloud sync {error.game_id} --keep-remote")
    typer.echo()
    typer.echo("Whichever save loses is kept in this game's version history.")
