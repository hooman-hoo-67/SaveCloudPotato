"""
Tests for machine-readable output.

A GUI and a person ask the same questions, so --json is a flag on the
same commands rather than a parallel set of them. What matters is that
the flag never changes what a command *does*, only how it says it, and
that stdout stays parseable on its own.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

from savecloud.cli import app
from savecloud.services.configuration import ConfigurationService
from savecloud.services.registry import RegistryService
from savecloud.services.sync import SyncService
from savecloud.utils import output

from tests.conftest import GAME_ID, write_save

runner = CliRunner()


def parsed(result):
    """
    Parse a command's stdout, failing loudly if it is not JSON.
    """

    return json.loads(result.stdout)


#
# The flag itself
#


def test_the_flag_defaults_to_off(registered_game):

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0

    assert "Registered Games" in result.stdout


def test_json_mode_does_not_leak_between_invocations(registered_game):
    """
    The flag is process-wide state, so it must be set per invocation.
    """

    runner.invoke(app, ["--json", "list"])

    result = runner.invoke(app, ["list"])

    assert "Registered Games" in result.stdout

    assert output.json_mode() is False


#
# list
#


def test_list_emits_every_registered_game(registered_game):

    result = runner.invoke(app, ["--json", "list"])

    assert result.exit_code == 0

    payload = parsed(result)

    assert payload["ok"] is True

    assert [game["game_id"] for game in payload["games"]] == [GAME_ID]


def test_list_emits_an_empty_array_when_nothing_is_registered():
    """
    An empty result is still a valid document, not prose.
    """

    payload = parsed(runner.invoke(app, ["--json", "list"]))

    assert payload["games"] == []


#
# info
#


def test_info_reports_game_storage_runtime_and_device(registered_game):

    payload = parsed(runner.invoke(app, ["--json", "info", GAME_ID]))

    assert payload["game"]["game_id"] == GAME_ID

    assert payload["storage"]["backend"] == "local"

    assert payload["runtime"]["status"]

    assert payload["device"]["working_save_path"]


def test_info_reports_a_missing_game_as_a_document(registered_game):
    """
    A failure a GUI can read, with the same exit code as before.
    """

    result = runner.invoke(app, ["--json", "info", "never-registered"])

    assert result.exit_code == 1

    payload = parsed(result)

    assert payload["ok"] is False

    assert payload["game_id"] == "never-registered"

    assert "not registered" in payload["error"]


#
# history
#


def test_history_lists_versions(registered_game, working_save):

    for index in range(3):
        write_save(working_save, f"session {index}")

        SyncService.sync(RegistryService.load_game(GAME_ID))

    payload = parsed(runner.invoke(app, ["--json", "history", GAME_ID]))

    assert payload["game_id"] == GAME_ID

    assert len(payload["versions"]) == 2      # the retention window


#
# sync
#


def test_sync_check_reports_the_action_without_applying_it(
    registered_game,
    working_save,
):

    write_save(working_save, "unsynced")

    payload = parsed(runner.invoke(app, ["--json", "sync", GAME_ID, "--check"]))

    assert payload["action"] == "upload"

    assert payload["applied"] is False


def test_sync_reports_what_it_did(registered_game, working_save):

    write_save(working_save, "progress")

    payload = parsed(runner.invoke(app, ["--json", "sync", GAME_ID]))

    assert payload["ok"] is True

    assert payload["action"] == "upload"

    assert payload["applied"] is True


def test_sync_reports_a_conflict_with_its_resolutions(
    registered_game,
    working_save,
):
    """
    The case a GUI must render as a choice rather than an error.
    """

    from tests.test_sync import advance_remote

    SyncService.sync(RegistryService.load_game(GAME_ID))

    advance_remote(GAME_ID, "remote progress")

    write_save(working_save, "local progress")

    result = runner.invoke(app, ["--json", "sync", GAME_ID])

    assert result.exit_code == 1

    payload = parsed(result)

    assert payload["ok"] is False

    assert payload["action"] == "conflict"

    assert payload["resolutions"] == ["keep-local", "keep-remote"]


def test_sync_all_reports_every_game():

    payload = parsed(runner.invoke(app, ["--json", "sync"]))

    assert payload["ok"] is True

    assert payload["games"] == []


#
# config and doctor
#


def test_config_show_reports_the_installation(registered_game):

    payload = parsed(runner.invoke(app, ["--json", "config", "show"]))

    assert payload["storage_backend"] == "local"

    assert payload["version_retention"] == ConfigurationService.load().version_retention

    assert payload["backend_available"] is True


def test_doctor_reports_findings_and_counts(registered_game):

    payload = parsed(runner.invoke(app, ["--json", "doctor", "--verbose"]))

    assert isinstance(payload["errors"], int)

    assert isinstance(payload["warnings"], int)

    assert payload["findings"]

    for finding in payload["findings"]:
        assert finding["severity"] in {"ok", "warning", "error"}


def test_doctor_keeps_its_exit_code(registered_game, monkeypatch):
    """
    --json must not change whether a command succeeds.
    """

    plain = runner.invoke(app, ["doctor"])

    structured = runner.invoke(app, ["--json", "doctor"])

    assert plain.exit_code == structured.exit_code


#
# pair
#


def test_pair_list_reports_what_storage_holds(registered_game, working_save):

    write_save(working_save, "progress")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    payload = parsed(runner.invoke(app, ["--json", "pair", "--list"]))

    assert payload["ok"] is True

    entry = next(game for game in payload["games"] if game["game_id"] == GAME_ID)

    assert entry["paired"] is True

    assert entry["registered"] is True
