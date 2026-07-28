"""
SaveCloud command-line interface.

Registration only. Every command delegates its work to services, so
nothing here contains business logic.
"""

import typer

from savecloud.commands import (
    config,
    doctor,
    download,
    export_save,
    history,
    import_save,
    info,
    init,
    list as list_command,
    pair,
    play,
    register,
    restore,
    snapshot,
    sync,
    unregister,
    upload,
)

app = typer.Typer(
    help="Steam Cloud for everything.",
    no_args_is_help=True,
)

#
# Installation
#

app.command("init")(init.init)

#
# Game management
#

app.command("register")(register.register)
app.command("unregister")(unregister.unregister)
app.command("list")(list_command.list)
app.command("info")(info.info)

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
