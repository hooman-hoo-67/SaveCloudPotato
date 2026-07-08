import typer

from savecloud.commands import init

app = typer.Typer(
    help="Steam Cloud for everything."
)

app.add_typer(init.app, name="init")


if __name__ == "__main__":
    app()
