"""
Choose whether this device synchronizes a game automatically.
"""

from __future__ import annotations

import typer

from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.utils import output
from savecloud.utils.output import require_game, require_profile


def autosync(
    game_id: str = typer.Argument(
        ...,
        help="Game to show or change.",
    ),
    state: str = typer.Argument(
        None,
        help="on or off. Omit to show the current setting.",
    ),
) -> None:
    """
    Show or change automatic synchronization for this device.
    """

    game = require_game(game_id)

    profile = require_profile(game_id)

    if state is None:

        if output.json_mode():

            output.emit(
                {
                    "ok": True,
                    "game_id": game_id,
                    "auto_sync": profile.enabled and game.manifest.sync_enabled,
                    "device": profile.enabled,
                    "game": game.manifest.sync_enabled,
                }
            )

            return

        typer.echo(
            f"{game_id}: automatic sync is "
            f"{'on' if profile.enabled else 'off'} on this device."
        )

        if not game.manifest.sync_enabled:
            typer.secho(
                "Synchronization is disabled for this game on every "
                "device, so this setting has no effect.",
                fg=typer.colors.YELLOW,
            )

        return

    wanted = state.strip().lower()

    if wanted not in {"on", "off"}:
        output.fail(
            f'Expected "on" or "off", not "{state}".',
            game_id=game_id,
        )

    profile.enabled = wanted == "on"

    DeviceService.save_profile(profile)

    if output.json_mode():

        output.emit(
            {
                "ok": True,
                "game_id": game_id,
                "auto_sync": profile.enabled and game.manifest.sync_enabled,
                "device": profile.enabled,
                "game": game.manifest.sync_enabled,
            }
        )

        return

    typer.secho(
        f"✓ Automatic sync {'enabled' if profile.enabled else 'disabled'} "
        f"for {game_id} on {SaveCloudLibrary.device_name()}.",
        fg=typer.colors.GREEN,
    )

    if not profile.enabled:
        typer.echo()
        typer.echo(
            f"Other devices are unaffected. `savecloud sync {game_id}` "
            f"still works when you ask for it by name."
        )
