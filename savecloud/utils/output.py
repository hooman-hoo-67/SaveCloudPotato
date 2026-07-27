"""
Shared command output helpers.

Commands must never import one another, so anything more than one
command needs to say lives here.
"""

from __future__ import annotations

import typer

from savecloud.services.sync import ConflictResolution, SyncConflictError


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
