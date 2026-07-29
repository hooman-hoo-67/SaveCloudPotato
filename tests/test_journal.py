"""
Tests for the record of what SaveCloud did.

`wrap` runs inside Steam with no terminal, so a failed upload during a
Gaming Mode session looks exactly like a successful one. The log is
the only place that difference survives.
"""

from __future__ import annotations

import logging

import pytest

from savecloud.services import journal
from savecloud.services.registry import RegistryService
from savecloud.services.sync import SyncService

from tests.conftest import GAME_ID, write_save


@pytest.fixture(autouse=True)
def fresh_journal():
    """
    Reconfigure for each test, since the installation moves.
    """

    journal.configure(force=True)

    yield

    logging.getLogger("savecloud").handlers.clear()


#
# Writing
#


def test_a_line_reaches_the_file():

    journal.logger("test").info("a thing happened")

    assert any("a thing happened" in line for line in journal.recent())


def test_the_file_lives_in_the_installation():

    from savecloud.config.constants import log_dir

    assert journal.path().parent == log_dir()


def test_nothing_raises_when_the_directory_cannot_be_made(monkeypatch):
    """
    A log is a convenience; a save is not. Failing to write one must
    never be why a session is lost.
    """

    def refuse(*args, **kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(journal.Path, "mkdir", refuse)

    journal.configure(force=True)

    journal.logger("test").info("still fine")


def test_recent_returns_nothing_when_there_is_no_log(monkeypatch, tmp_path):

    monkeypatch.setattr(journal, "path", lambda: tmp_path / "absent.log")

    assert journal.recent() == []


def test_recent_returns_the_newest_lines():

    log = journal.logger("test")

    for index in range(10):
        log.info("line %s", index)

    recent = journal.recent(3)

    assert len(recent) == 3

    assert "line 9" in recent[-1]


def test_debug_is_off_unless_asked_for(monkeypatch):
    """
    Per-file transfer detail is the difference between a log worth
    reading and a log worth grepping.
    """

    monkeypatch.delenv(journal.LEVEL_ENV, raising=False)

    journal.configure(force=True)

    journal.logger("test").debug("too much detail")

    assert not any("too much detail" in line for line in journal.recent())


def test_debug_can_be_turned_on_for_a_bug_report(monkeypatch):

    monkeypatch.setenv(journal.LEVEL_ENV, "DEBUG")

    journal.configure(force=True)

    journal.logger("test").debug("the detail")

    assert any("the detail" in line for line in journal.recent())


def test_configuring_twice_does_not_double_every_line():

    journal.configure(force=True)

    journal.configure(force=True)

    journal.logger("test").info("said once")

    written = [line for line in journal.recent() if "said once" in line]

    assert len(written) == 1


#
# What it records
#


def test_a_sync_records_what_it_decided(registered_game, working_save):

    write_save(working_save, "progress")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    assert any(
        "comparison says upload" in line for line in journal.recent()
    )


def test_an_unreachable_backend_is_recorded(registered_game, monkeypatch):
    """
    The case with nowhere to print: this is the whole point.
    """

    from savecloud.services.sync import StorageUnavailableError
    from savecloud.storage import LocalStorageBackend

    monkeypatch.setattr(
        LocalStorageBackend, "available", classmethod(lambda cls: False)
    )

    with pytest.raises(StorageUnavailableError):
        SyncService.sync(RegistryService.load_game(GAME_ID))

    assert any("storage unavailable" in line for line in journal.recent())


def test_a_captured_session_is_recorded(registered_game, working_save):

    from savecloud.services.autosync import AutoSyncService

    write_save(working_save, "played")

    AutoSyncService.play(RegistryService.load_game(GAME_ID))

    written = "\n".join(journal.recent())

    assert "exited with 0" in written

    assert "session captured" in written


def test_a_failed_upload_after_a_session_is_recorded(
    registered_game,
    working_save,
    monkeypatch,
):
    """
    The failure a Gaming Mode session cannot show anyone.
    """

    from savecloud.services.autosync import AutoSyncService
    from savecloud.storage import LocalStorageBackend

    SyncService.sync(RegistryService.load_game(GAME_ID))

    monkeypatch.setattr(
        LocalStorageBackend, "available", classmethod(lambda cls: False)
    )

    write_save(working_save, "played offline")

    AutoSyncService.play(RegistryService.load_game(GAME_ID))

    assert any(
        "upload failed, save kept locally" in line
        for line in journal.recent()
    )


def test_an_unexpected_exit_is_recorded(registered_game, working_save, tmp_path):

    from savecloud.services.autosync import AutoSyncService
    from tests.conftest import register_game

    RegistryService.delete_registry(GAME_ID)

    working = tmp_path / "crashing"

    write_save(working, "before")

    game = register_game(working, launch_command="false")

    AutoSyncService.play(game)

    assert any(
        "unexpected exit, captured but not published" in line
        for line in journal.recent()
    )


#
# Reading it back
#


def test_the_command_shows_recent_lines():

    from typer.testing import CliRunner

    from savecloud.cli import app

    journal.logger("test").info("something worth reading")

    result = CliRunner().invoke(app, ["logs"])

    assert result.exit_code == 0

    assert "something worth reading" in result.output


def test_the_command_can_report_the_path():

    from typer.testing import CliRunner

    from savecloud.cli import app

    result = CliRunner().invoke(app, ["logs", "--path"])

    assert str(journal.path()) in result.output


def test_the_command_emits_json():

    import json

    from typer.testing import CliRunner

    from savecloud.cli import app

    journal.logger("test").info("a recorded line")

    result = CliRunner().invoke(app, ["--json", "logs"])

    payload = json.loads(result.stdout)

    assert payload["ok"] is True

    assert any("a recorded line" in line for line in payload["lines"])


def test_the_command_says_so_when_nothing_is_logged(monkeypatch, tmp_path):

    from typer.testing import CliRunner

    from savecloud.cli import app

    monkeypatch.setattr(journal, "path", lambda: tmp_path / "absent.log")

    result = CliRunner().invoke(app, ["logs"])

    assert "Nothing logged yet" in result.output


#
# Safety
#


def test_credentials_never_reach_the_log(registered_game, working_save, monkeypatch):
    """
    A log that cannot be pasted into a bug report is not much use, so
    nothing secret may end up in it.
    """

    from savecloud.services.credentials import CredentialService

    monkeypatch.setenv(journal.LEVEL_ENV, "DEBUG")

    journal.configure(force=True)

    CredentialService.save(
        "dropbox",
        {
            "app_key": "SECRETKEY",
            "app_secret": "SECRETSECRET",
            "refresh_token": "SECRETTOKEN",
        },
    )

    write_save(working_save, "progress")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    written = "\n".join(journal.recent(500))

    for secret in ("SECRETKEY", "SECRETSECRET", "SECRETTOKEN"):
        assert secret not in written
