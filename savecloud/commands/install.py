"""
Put SaveCloud on PATH and in the applications menu.
"""

from __future__ import annotations

import typer

from savecloud.services import integration
from savecloud.utils import output


def install(
    remove: bool = typer.Option(
        False,
        "--remove",
        help="Undo it instead.",
    ),
) -> None:
    """
    Make `savecloud` available in a terminal and in the menu.
    """

    if remove:
        result = integration.remove()

    else:

        if not integration.is_packaged():
            output.fail(
                "This build is already on PATH - it was installed with "
                "pip, not downloaded as an AppImage.",
            )

        result = integration.install()

    if output.json_mode():

        output.emit(
            {
                "ok": result.ok,
                "message": result.message,
                "created": result.created,
                "warnings": result.warnings,
            }
        )

        raise typer.Exit(code=0 if result.ok else 1)

    if not result.ok:
        typer.secho(f"✗ {result.message}", fg=typer.colors.RED)

        raise typer.Exit(code=1)

    typer.secho(f"✓ {result.message}", fg=typer.colors.GREEN)

    for path in result.created:
        typer.echo(f"  {path}")

    for warning in result.warnings:
        typer.echo()

        typer.secho(warning, fg=typer.colors.YELLOW)
