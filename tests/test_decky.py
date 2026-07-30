"""
The Decky plugin's backend.

Decky supplies the `decky` module by injecting it, and runs the backend
as root under its own interpreter - none of which exists here. So the
module is loaded by hand against a stand-in, and pointed at a fake
`savecloud` that can be made to misbehave on demand.

What is worth testing is the part that has nothing to do with Decky: an
interface in Gaming Mode has nowhere to show a traceback, so every way a
command can fail has to arrive as a document instead.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest

#
# The backend targets SteamOS: it looks accounts up in the POSIX user
# database and the fakes below are shell scripts. Neither exists on
# Windows, and nor does Decky, so the whole file steps aside there.
#

pwd = pytest.importorskip("pwd")

BACKEND = Path(__file__).resolve().parent.parent / "decky" / "main.py"


def load(home: Path, user: str = "nobody-at-all"):
    """
    Load the backend with a stand-in for Decky's injected module.

    The user name is deliberately one that does not exist, so the
    fallback to the current account is what runs: tests must not depend
    on the machine having a `deck` account, and must not try to change
    user.
    """

    stub = types.ModuleType("decky")

    stub.HOME = str(home)
    stub.USER = user

    logger = types.SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        error=lambda *a, **k: None,
        exception=lambda *a, **k: None,
    )

    stub.logger = logger

    previous = sys.modules.get("decky")

    sys.modules["decky"] = stub

    try:
        spec = importlib.util.spec_from_file_location("decky_main", BACKEND)

        module = importlib.util.module_from_spec(spec)

        spec.loader.exec_module(module)

    finally:
        if previous is None:
            del sys.modules["decky"]

        else:
            sys.modules["decky"] = previous

    return module


def install_fake(home: Path, body: str) -> Path:
    """
    Put an executable script where the backend looks for `savecloud`.
    """

    command = home / ".local" / "bin" / "savecloud"

    command.parent.mkdir(parents=True, exist_ok=True)

    command.write_text(body, encoding="utf-8")

    command.chmod(0o755)

    return command


def run(coroutine):
    """
    Drive one backend route to completion.
    """

    return asyncio.run(coroutine)


#
# Finding the command
#


def test_nothing_installed_is_reported_not_raised(tmp_path):

    module = load(tmp_path)

    assert module.locate() is None

    answer = run(module.Plugin().installed())

    assert answer["ok"] is False
    assert "not installed" in answer["error"]


def test_an_installed_command_is_found(tmp_path):

    module = load(tmp_path)

    command = install_fake(tmp_path, "#!/bin/sh\necho 'savecloud 1.2.3'\n")

    assert module.locate() == command

    answer = run(module.Plugin().installed())

    assert answer["ok"] is True
    assert answer["version"] == "savecloud 1.2.3"


def test_a_command_that_cannot_be_executed_is_not_found(tmp_path):

    module = load(tmp_path)

    command = install_fake(tmp_path, "#!/bin/sh\ntrue\n")

    command.chmod(0o644)

    assert module.locate() is None


def test_an_unpacked_appimage_is_found(tmp_path):
    """
    Someone who never ran `savecloud install` still has the AppImage.
    """

    module = load(tmp_path)

    command = tmp_path / "Downloads" / "SaveCloud-x86_64.AppImage"

    command.parent.mkdir(parents=True)

    command.write_text("#!/bin/sh\ntrue\n", encoding="utf-8")

    command.chmod(0o755)

    assert module.locate() == command


#
# Reading answers
#


def test_a_json_document_is_passed_through(tmp_path):

    module = load(tmp_path)

    install_fake(tmp_path, '#!/bin/sh\necho \'{"ok": true, "games": []}\'\n')

    answer = run(module.Plugin().games())

    assert answer == {"ok": True, "games": []}


def test_a_failing_command_is_believed_over_its_document(tmp_path):
    """
    The exit code decides success; the document only explains it.

    A command that prints a document and then fails has failed, and an
    interface that trusted the document would report the opposite.
    """

    module = load(tmp_path)

    install_fake(tmp_path, '#!/bin/sh\necho \'{"error": "no"}\'\nexit 1\n')

    answer = run(module.Plugin().games())

    assert answer["ok"] is False
    assert answer["error"] == "no"


def test_a_document_that_says_it_failed_keeps_saying_so(tmp_path):
    """
    An explicit `ok` in the document is not overwritten.
    """

    module = load(tmp_path)

    install_fake(
        tmp_path,
        '#!/bin/sh\necho \'{"ok": false, "error": "conflict"}\'\nexit 1\n',
    )

    answer = run(module.Plugin().games())

    assert answer["ok"] is False
    assert answer["error"] == "conflict"


def test_prose_becomes_an_error_rather_than_a_parse_failure(tmp_path):
    """
    A command's own words beat a JSONDecodeError.
    """

    module = load(tmp_path)

    install_fake(
        tmp_path,
        "#!/bin/sh\necho 'Usage: savecloud'\necho 'No such command.'\n",
    )

    answer = run(module.Plugin().games())

    assert answer["ok"] is False
    assert answer["error"] == "No such command."


def test_silence_falls_back_to_standard_error(tmp_path):

    module = load(tmp_path)

    install_fake(tmp_path, "#!/bin/sh\necho 'it broke' >&2\nexit 3\n")

    answer = run(module.Plugin().games())

    assert answer["ok"] is False
    assert answer["error"] == "it broke"


def test_silence_with_nothing_to_say_reports_the_exit_code(tmp_path):

    module = load(tmp_path)

    install_fake(tmp_path, "#!/bin/sh\nexit 4\n")

    answer = run(module.Plugin().games())

    assert answer["ok"] is False
    assert "4" in answer["error"]


def test_a_command_that_hangs_gives_up(tmp_path, monkeypatch):
    """
    A spinner that never stops is worse than a message.
    """

    module = load(tmp_path)

    monkeypatch.setattr(module, "TIMEOUT_SECONDS", 1)

    install_fake(tmp_path, "#!/bin/sh\nsleep 30\n")

    answer = run(module.Plugin().games())

    assert answer["ok"] is False
    assert "did not finish" in answer["error"]


#
# Arguments
#


def test_every_route_asks_for_json(tmp_path):
    """
    The backend parses documents, so it must always request one.
    """

    module = load(tmp_path)

    install_fake(
        tmp_path,
        '#!/bin/sh\necho "{\\"ok\\": true, \\"argv\\": \\"$*\\"}"\n',
    )

    plugin = module.Plugin()

    for route, expected in (
        (plugin.games(), "--json list"),
        (plugin.detail("demo"), "--json info demo"),
        (plugin.check("demo"), "--json sync demo --check"),
        (plugin.check_all(), "--json sync --check"),
        (plugin.sync("demo"), "--json sync demo"),
        (plugin.sync_all(), "--json sync"),
        (plugin.resolve("demo", "local"), "--json sync demo --keep-local"),
        (plugin.resolve("demo", "remote"), "--json sync demo --keep-remote"),
        (plugin.logs(7), "--json logs --lines 7"),
    ):
        assert run(route)["argv"] == expected


def test_an_unknown_resolution_never_reaches_the_command(tmp_path):
    """
    `--keep-sideways` would be a usage error; refusing is clearer.
    """

    module = load(tmp_path)

    install_fake(tmp_path, "#!/bin/sh\necho should-not-run\nexit 1\n")

    answer = run(module.Plugin().resolve("demo", "sideways"))

    assert answer["ok"] is False
    assert "sideways" in answer["error"]


#
# Which user the command runs as
#


def test_the_command_runs_as_the_desktop_user(tmp_path):
    """
    Not as root, and with the desktop user's HOME.

    This is the whole reason the backend shells out instead of importing
    SaveCloud. A command run as root against the user's HOME leaves
    root-owned files in their save library, which locks them out of it.
    """

    module = load(tmp_path)

    install_fake(
        tmp_path,
        '#!/bin/sh\necho "{\\"ok\\": true, \\"whoami\\": \\"$(id -u)\\", '
        '\\"home\\": \\"$HOME\\", \\"cwd\\": \\"$PWD\\"}"\n',
    )

    answer = run(module.Plugin().games())

    assert answer["home"] == str(tmp_path)
    assert answer["cwd"] == str(tmp_path)

    #
    # Under a test runner this is already the desktop user, so the
    # assertion is that nothing escalated rather than that anything
    # dropped. The drop itself only happens when Decky runs it as root,
    # which cannot be reproduced here without being root.
    #
    assert answer["whoami"] == str(os.getuid())


def test_an_unknown_user_falls_back_rather_than_failing(tmp_path):
    """
    A name that resolves to nobody must not stop the plugin loading.

    Deliberately about `_user()` and not about running anything: which
    account a name resolves to is a property of the machine, and a test
    that ran a command as whatever `deck` happens to be here would pass
    or fail depending on who exists.
    """

    module = load(tmp_path, user="nobody-at-all")

    assert module._user().pw_uid == os.getuid()


def test_an_unset_user_assumes_steamos(tmp_path):
    """
    Decky not saying whose session it is means SteamOS, and `deck`.
    """

    module = load(tmp_path, user="")

    try:
        expected = pwd.getpwnam("deck").pw_uid

    except KeyError:
        expected = os.getuid()

    assert module._user().pw_uid == expected


def test_certificate_trust_reaches_the_command(tmp_path, monkeypatch):
    """
    A network that inspects TLS must not break only in Gaming Mode.

    Trust is configured through the environment and nowhere else. The
    backend builds its environment rather than inheriting one, so
    without carrying these across, a Deck that syncs fine from a
    terminal would fail from the panel with a certificate error and no
    obvious reason why.
    """

    module = load(tmp_path)

    monkeypatch.setenv("SSL_CERT_FILE", "/etc/ssl/somewhere.pem")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")

    install_fake(
        tmp_path,
        "#!/bin/sh\n"
        'echo "{\\"ok\\": true, \\"ca\\": \\"$SSL_CERT_FILE\\", '
        '\\"proxy\\": \\"$HTTPS_PROXY\\"}"\n',
    )

    answer = run(module.Plugin().games())

    assert answer["ca"] == "/etc/ssl/somewhere.pem"
    assert answer["proxy"] == "http://proxy:3128"


def test_an_unset_variable_is_not_invented(tmp_path, monkeypatch):
    """
    Passing an empty value through is worse than passing nothing.
    """

    module = load(tmp_path)

    monkeypatch.delenv("SSL_CERT_FILE", raising=False)

    install_fake(
        tmp_path,
        "#!/bin/sh\n"
        'echo "{\\"ok\\": true, \\"seen\\": \\"${SSL_CERT_FILE-unset}\\"}"\n',
    )

    assert run(module.Plugin().games())["seen"] == "unset"


def test_qt_is_told_there_is_no_display(tmp_path):
    """
    The one binary serves both interfaces, and dispatches on argv.

    A CLI invocation never opens a window, but Qt is imported either way
    on some builds, and a plugin backend has no display to reach.
    """

    module = load(tmp_path)

    install_fake(
        tmp_path,
        "#!/bin/sh\n"
        'echo "{\\"ok\\": true, \\"qt\\": \\"$QT_QPA_PLATFORM\\"}"\n',
    )

    assert run(module.Plugin().games())["qt"] == "offscreen"


@pytest.mark.parametrize("route", ["games", "check_all", "sync_all"])
def test_no_route_raises_when_nothing_is_installed(tmp_path, route):

    module = load(tmp_path)

    plugin = module.Plugin()

    answer = run(getattr(plugin, route)())

    assert answer["ok"] is False
    assert "not installed" in answer["error"]
