import typer
from rich.console import Console

from .library import SaveCloudLibrary

app = typer.Typer(
    help="Steam Cloud for everything."
)

console = Console()


@app.callback()
def main():
    """
    SaveCloud CLI.
    """
    pass


@app.command()
def init():
    """
    Initialize the SaveCloud filesystem.
    """

    if SaveCloudLibrary.validate():
        console.print("[yellow]SaveCloud is already initialized.[/yellow]")
        raise typer.Exit()

    console.print("[bold cyan]Initializing SaveCloud...[/bold cyan]")

    created = SaveCloudLibrary.initialize()

    for directory in created:
        console.print(f"[green]✓[/green] {directory.name}")

    console.print("\n[bold green]Initialization complete.[/bold green]")


if __name__ == "__main__":
    app()
