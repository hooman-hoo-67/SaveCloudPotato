import typer

from savecloud.commands import init
from savecloud.commands.register import app as register_app
from savecloud.commands.list import app as list_app
from savecloud.commands.info import app as info_app
from savecloud.commands.unregister import app as unregister_app
from savecloud.commands import import_save
from savecloud.commands import export_save
from savecloud.commands import snapshot
from savecloud.commands import history
from savecloud.commands import restore
from savecloud.commands import download
from savecloud.commands import sync
from savecloud.commands import upload

app = typer.Typer(help="Steam Cloud for everything.")

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

app.add_typer(
    import_save.app,
    name="import",
)

app.add_typer(
    export_save.app,
    name="export",
)

app.add_typer(
    snapshot.app,
    name="snapshot",
)

app.add_typer(
    history.app,
    name="history",
)

app.add_typer(
    restore.app,
    name="restore",
)

app.add_typer(
    upload.app,
    name="upload",
)

app.add_typer(
    download.app,
    name="download",
)

app.add_typer(
    sync.app,
    name="sync",
)

if __name__ == "__main__":
    app()
