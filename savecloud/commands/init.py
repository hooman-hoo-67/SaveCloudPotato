import typer
from rich.console import Console

from savecloud.services.library import SaveCloudLibrary

app = typer.Typer()

console = Console()


@app.callback(invoke_without_command=True)
def init():
    """Initialize the SaveCloud filesystem."""

    if SaveCloudLibrary.validate():
        console.print("[yellow]SaveCloud is already initialized.[/yellow]")
        raise typer.Exit()

    console.print("[bold cyan]Initializing SaveCloud...[/bold cyan]")

    created = SaveCloudLibrary.initialize()

    for directory in created:
        console.print(f"[green]✓[/green] {directory.name}")

    console.print("\n[bold green]Initialization complete.[/bold green]")
