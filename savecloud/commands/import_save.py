"""
Import a game's working save into the SaveCloud library.
"""

from __future__ import annotations

import typer

from savecloud.services.device import DeviceService
from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService
from savecloud.services.library import SaveCloudLibrary

app = typer.Typer()


@app.callback(invoke_without_command=True)
def import_save(
    game_id: str,
) -> None:
    """
    Import the current working save into the SaveCloud library.
    """

    game = RegistryService.load_game(
        game_id,
    )

    profile = DeviceService.load_profile(
        SaveCloudLibrary.device_id(),
        game_id,
    )

    SaveService.import_save(
        game,
        profile,
    )

    typer.secho(
        "✓ Save imported successfully.",
        fg=typer.colors.GREEN,
    )
