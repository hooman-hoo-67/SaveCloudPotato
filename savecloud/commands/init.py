"""
Initialize the SaveCloud installation.
"""

import typer
from rich.console import Console

from savecloud.services.configuration import ConfigurationService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService

console = Console()


def init():
    """Initialize the SaveCloud filesystem."""

    if SaveCloudLibrary.validate() and ConfigurationService.exists():
        console.print("[yellow]SaveCloud is already initialized.[/yellow]")
        raise typer.Exit()

    console.print("[bold cyan]Initializing SaveCloud...[/bold cyan]")

    created = SaveCloudLibrary.initialize()

    for directory in created:
        console.print(f"[green]✓[/green] {directory.name}")

    if not ConfigurationService.exists():

        config = ConfigurationService.default()

        #
        # Adopt a backend recorded by an older installation, where
        # storage was configured per game rather than per installation.
        #

        legacy = RegistryService.legacy_storage_backend()

        if legacy is not None:

            config.storage_backend = legacy

            console.print(
                f"[green]✓[/green] adopted storage backend "
                f"[bold]{legacy}[/bold] from previously registered games",
            )

        ConfigurationService.save(config)

        console.print("[green]✓[/green] config.json")

    console.print("\n[bold green]Initialization complete.[/bold green]")

    config = ConfigurationService.load()

    console.print(
        f"\nStorage backend : [bold]{config.storage_backend}[/bold]"
        f"\nStorage root    : [bold]{config.storage_root}[/bold]"
        f"\n\nChange these with [bold]savecloud config[/bold]."
    )
