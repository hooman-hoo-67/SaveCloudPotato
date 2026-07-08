import typer

from savecloud.commands import init
from savecloud.commands.register import app as register_app
from savecloud.commands.list import app as list_app
from savecloud.commands.info import app as info_app
from savecloud.commands.unregister import app as unregister_app

app = typer.Typer(
    help="Steam Cloud for everything."
)

app.add_typer(
    init.app,
    name="init",
)

app.add_typer(
    register_app,
    name="register",
)

app.add_typer(
    list_app,
    name="list",
)

app.add_typer(
    info_app,
    name="info",
)

app.add_typer(
    unregister_app,
    name="unregister",
)

if __name__ == "__main__":
    app()
