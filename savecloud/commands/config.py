"""
Manage installation-wide configuration.
"""

from __future__ import annotations

from pathlib import Path

import typer

from savecloud.services.configuration import ConfigurationService
from savecloud.services.save import SaveService
from savecloud.services.sync import SyncService
from savecloud.storage import StorageRegistry

app = typer.Typer(
    help="Manage installation-wide configuration.",
)


@app.command("show")
def show() -> None:
    """
    Display the current configuration.
    """

    config = ConfigurationService.load()

    backend = StorageRegistry.get(config.storage_backend)

    typer.echo("Installation Configuration")
    typer.echo("--------------------------")
    typer.echo()

    typer.echo(f"Config File     : {ConfigurationService.path()}")

    if not ConfigurationService.exists():
        typer.secho(
            "                  (not created yet, showing defaults)",
            fg=typer.colors.YELLOW,
        )

    typer.echo()

    typer.echo(f"Storage Backend : {config.storage_backend}")

    typer.echo(f"Storage Root    : {config.storage_root}")

    if config.version_retention == 0:
        typer.echo("Version History : every version kept")

    else:
        typer.echo(
            f"Version History : {config.version_retention} versions per game"
        )

    typer.echo()

    if backend is None:
        typer.secho(
            f'Backend "{config.storage_backend}" is not registered.',
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    if backend.available():
        typer.secho(
            "Status          : available",
            fg=typer.colors.GREEN,
        )

    else:
        typer.secho(
            "Status          : unavailable",
            fg=typer.colors.YELLOW,
        )

        typer.echo(f"                  {backend.unavailable_reason()}")


@app.command("backend")
def backend(
    name: str = typer.Argument(
        None,
        help="Storage backend to activate.",
    ),
) -> None:
    """
    Show or change the active storage backend.
    """

    if name is None:
        typer.echo("Available storage backends")
        typer.echo("--------------------------")
        typer.echo()

        active = ConfigurationService.load().storage_backend

        for backend_name in StorageRegistry.names():

            marker = "*" if backend_name == active else " "

            implementation = StorageRegistry.get(backend_name)

            assert implementation is not None

            typer.echo(f" {marker} {backend_name:<12} {implementation.display_name()}")

        typer.echo()
        typer.echo("* currently active")

        return

    try:
        config = ConfigurationService.set_backend(name)

    except ValueError as error:
        typer.secho(
            str(error),
            fg=typer.colors.RED,
        )

        typer.echo(
            f"Available backends: {', '.join(StorageRegistry.names())}",
        )

        raise typer.Exit(code=1)

    typer.secho(
        f"✓ Storage backend set to {config.storage_backend}.",
        fg=typer.colors.GREEN,
    )

    implementation = StorageRegistry.get(config.storage_backend)

    if implementation is not None and not implementation.available():
        typer.secho(
            implementation.unavailable_reason(),
            fg=typer.colors.YELLOW,
        )


@app.command("root")
def root(
    path: Path = typer.Argument(
        None,
        help="Directory the storage backend should use.",
    ),
) -> None:
    """
    Show or change the storage root directory.
    """

    if path is None:
        typer.echo(ConfigurationService.load().storage_root)
        return

    config = ConfigurationService.set_root(path)

    typer.secho(
        f"✓ Storage root set to {config.storage_root}.",
        fg=typer.colors.GREEN,
    )


@app.command("retention")
def retention(
    count: int = typer.Argument(
        None,
        help="Versions to keep per game. 0 keeps every version.",
    ),
) -> None:
    """
    Show or change how many historical versions are kept.
    """

    if count is None:
        current = ConfigurationService.load().version_retention

        if current == 0:
            typer.echo("0 (every version is kept)")

        else:
            typer.echo(f"{current} versions per game, plus the current save")

        return

    try:
        config = ConfigurationService.set_retention(count)

    except ValueError as error:
        typer.secho(str(error), fg=typer.colors.RED)

        raise typer.Exit(code=1)

    if config.version_retention == 0:
        typer.secho(
            "✓ Every version will be kept.",
            fg=typer.colors.GREEN,
        )

        return

    typer.secho(
        f"✓ Keeping {config.version_retention} versions per game.",
        fg=typer.colors.GREEN,
    )

    #
    # Trimming normally happens as versions are created, which would
    # leave a game nobody has played still holding its old history.
    # Setting the window applies it.
    #

    removed = SaveService.apply_retention(config.version_retention)

    for game_id, versions in sorted(removed.items()):
        typer.echo(
            f"  {game_id}: removed {len(versions)} version"
            f"{'' if len(versions) == 1 else 's'} locally"
        )

    try:
        remote = SyncService.prune_remote(config.version_retention)

    #
    # Any backend failure is reported rather than raised: the setting
    # was saved, and storage catches up on the next upload regardless.
    #

    except Exception as error:
        typer.echo()
        typer.secho(
            f"Storage was not trimmed: {error}",
            fg=typer.colors.YELLOW,
        )

        typer.echo("It will be trimmed on the next upload.")

        return

    for game_id, versions in sorted(remote.items()):
        typer.echo(
            f"  {game_id}: removed {len(versions)} version"
            f"{'' if len(versions) == 1 else 's'} from storage"
        )

    if not removed and not remote:
        typer.echo()
        typer.echo("Nothing to remove; history is already within the window.")


@app.command("provider")
def provider(
    name: str = typer.Argument(
        None,
        help="Backend to set up. Defaults to the active one.",
    ),
) -> None:
    """
    Set up credentials for a storage backend.
    """

    if name is None:
        name = ConfigurationService.load().storage_backend

    backend = StorageRegistry.get(name)

    if backend is None:
        typer.secho(
            f'Unknown storage backend: "{name}".',
            fg=typer.colors.RED,
        )

        typer.echo(f"Available backends: {', '.join(StorageRegistry.names())}")

        raise typer.Exit(code=1)

    if not backend.requires_setup():
        typer.echo(
            f"{backend.display_name()} needs no credentials. "
            f"Configure it with `savecloud config root <path>`."
        )

        return

    backend.setup()


@app.command("validate")
def validate() -> None:
    """
    Verify that the configured backend is usable.
    """

    config = ConfigurationService.load()

    implementation = StorageRegistry.get(config.storage_backend)

    if implementation is None:
        typer.secho(
            f'Unknown storage backend: "{config.storage_backend}".',
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    if not implementation.available():
        typer.secho(
            implementation.unavailable_reason(),
            fg=typer.colors.RED,
        )

        raise typer.Exit(code=1)

    typer.secho(
        f"✓ {implementation.display_name()} backend is available "
        f"at {config.storage_root}.",
        fg=typer.colors.GREEN,
    )
