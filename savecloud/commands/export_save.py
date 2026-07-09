"""
Export a managed save from the SaveCloud library.
"""

from __future__ import annotations

import typer

from savecloud.services.device import DeviceService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService


app = typer.Typer()


@app.callback(invoke_without_command=True)
def export_save(
    game_id: str,
) -> None:
    """
    Export the managed save to the working save directory.
    """

    game = RegistryService.load_game(
        game_id,
    )

    profile = DeviceService.load_profile(
        SaveCloudLibrary.device_id(),
        game_id,
    )

    SaveService.export_save(
        game,
        profile,
    )

    typer.secho(
        "✓ Save exported successfully.",
        fg=typer.colors.GREEN,
    )
