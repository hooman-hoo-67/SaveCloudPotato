"""
SaveCloud command-line interface.

Registration only. Every command delegates its work to services, so
nothing here contains business logic.
"""

import typer

from savecloud.commands import (
    autosync,
    config,
    doctor,
    download,
    export_save,
    history,
    import_save,
    info,
    init,
    install as install_command,
    list as list_command,
    pair,
    play,
    register,
    restore,
    snapshot,
    sync,
    unregister,
    upload,
    wrap,
)
from savecloud.utils import output

app = typer.Typer(
    help="Steam Cloud for everything.",
    no_args_is_help=True,
)


@app.callback()
def main(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable output instead of prose.",
    ),
) -> None:
    """
    Steam Cloud for everything.
    """

    #
    # Set before any command runs, so a command need only ask whether
    # it was requested. A flag rather than a parallel set of commands:
    # a GUI and a person ask the same questions, and two code paths
    # answering them would drift apart.
    #

    output.set_json(json_output)

#
# Installation
#

app.command("init")(init.init)
app.command("install")(install_command.install)

#
# Game management
#

app.command("register")(register.register)
app.command("unregister")(unregister.unregister)
app.command("list")(list_command.list)
app.command("info")(info.info)
app.command("autosync")(autosync.autosync)

#
# Save management
#

app.command("import")(import_save.import_save)
app.command("export")(export_save.export_save)
app.command("snapshot")(snapshot.snapshot)
app.command("history")(history.history)
app.command("restore")(restore.restore)

#
# Synchronization
#

app.command("upload")(upload.upload)
app.command("download")(download.download)
app.command("sync")(sync.sync)
app.command("pair")(pair.pair)

#
# Gameplay
#

app.command("play")(play.play)

#
# Steam hands the real command through after a -- separator, so
# unknown options must reach the game rather than click.
#

app.command(
    "wrap",
    context_settings={
        "ignore_unknown_options": True,
        "allow_interspersed_args": False,
    },
)(wrap.wrap)

#
# Diagnostics
#

app.command("doctor")(doctor.doctor)

#
# Configuration
#

app.add_typer(
    config.app,
    name="config",
)


if __name__ == "__main__":
    app()
