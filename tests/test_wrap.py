"""
Tests for the Steam launch-options wrapper.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from savecloud.cli import app
from savecloud.services.autosync import AutoSyncService, UntrackableLaunchError
from savecloud.services.device import DeviceService
from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService
from savecloud.services.sync import SyncAction, SyncConflictError, SyncService
from savecloud.storage import LocalStorageBackend

from tests.conftest import GAME_ID, read_save, register_game, write_save
from tests.test_sync import advance_remote

runner = CliRunner()


def writing_command(working_save, contents: str) -> list[str]:
    """
    Build an argv that writes save data, standing in for a game.
    """

    return [
        "sh",
        "-c",
        f"printf '{contents}' > {working_save / 'save.dat'}",
    ]


#
# Service
#


def test_wrap_runs_the_command_and_uploads(registered_game, working_save):

    result = AutoSyncService.wrap(
        registered_game,
        writing_command(working_save, "after playing"),
    )

    assert result.exit_code == 0
    assert result.uploaded is True

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "after playing"


def test_wrap_synchronizes_before_running(registered_game, working_save):

    result = AutoSyncService.wrap(registered_game, ["true"])

    assert result.pre_launch is SyncAction.UPLOAD


def test_wrap_pulls_remote_progress_first(registered_game, working_save):

    SyncService.sync(registered_game)

    advance_remote(GAME_ID, "progress from elsewhere")

    result = AutoSyncService.wrap(
        RegistryService.load_game(GAME_ID),
        ["true"],
    )

    assert result.pre_launch is SyncAction.DOWNLOAD

    assert read_save(working_save) == "progress from elsewhere"


def test_wrap_ignores_the_configured_launcher(registered_game, device_id):
    """
    Steam already answered "how is this started"; no launcher applies.
    """

    profile = DeviceService.load_profile(device_id, GAME_ID)

    profile.launcher = "nonexistent"

    DeviceService.save_profile(profile)

    result = AutoSyncService.wrap(registered_game, ["true"])

    assert result.exit_code == 0


def test_wrap_passes_through_a_failing_exit_code(registered_game):

    result = AutoSyncService.wrap(registered_game, ["false"])

    assert result.exit_code == 1
    assert result.uploaded is False


def test_a_crash_under_wrap_does_not_upload(registered_game, working_save):
    """
    The half-written save a crash leaves behind must not be published.
    """

    SyncService.sync(registered_game)

    crashing = [
        "sh",
        "-c",
        f"printf 'half written' > {working_save / 'save.dat'}; exit 1",
    ]

    result = AutoSyncService.wrap(
        RegistryService.load_game(GAME_ID),
        crashing,
    )

    assert result.exit_code == 1
    assert result.uploaded is False

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "original"


def test_wrap_refuses_an_empty_command(registered_game):

    with pytest.raises(ValueError):
        AutoSyncService.wrap(registered_game, [])


def test_wrap_aborts_on_a_conflict(registered_game, working_save):

    SyncService.sync(registered_game)

    write_save(working_save, "local progress")

    advance_remote(GAME_ID, "remote progress")

    with pytest.raises(SyncConflictError):
        AutoSyncService.wrap(
            RegistryService.load_game(GAME_ID),
            ["true"],
        )


def test_wrap_creates_a_version_for_the_session(registered_game, working_save):

    AutoSyncService.wrap(
        registered_game,
        writing_command(working_save, "session one"),
    )

    game = RegistryService.load_game(GAME_ID)

    assert len(SaveService.list_versions(game)) >= 1

    assert read_save(SaveService.current_save(game)) == "session one"


#
# play refuses launchers that cannot report exit
#


def test_play_refuses_the_steam_launcher(registered_game, device_id):
    """
    Waiting on `steam -applaunch` returns immediately, so capturing
    afterwards would record the save from before the session.
    """

    profile = DeviceService.load_profile(device_id, GAME_ID)

    profile.launcher = "steam"
    profile.launch_command = "2050650"

    DeviceService.save_profile(profile)

    with pytest.raises(UntrackableLaunchError):
        AutoSyncService.play(registered_game)


def test_play_refuses_before_synchronizing(registered_game, device_id):

    profile = DeviceService.load_profile(device_id, GAME_ID)

    profile.launcher = "steam"

    DeviceService.save_profile(profile)

    with pytest.raises(UntrackableLaunchError):
        AutoSyncService.play(registered_game)

    #
    # Nothing was uploaded, so no false "synchronized" state exists.
    #

    assert not LocalStorageBackend.exists(GAME_ID)


#
# CLI
#


def test_cli_wrap_runs_a_command(tmp_path):

    working = tmp_path / "working"

    write_save(working, "before")

    register_game(working)

    result = runner.invoke(
        app,
        [
            "wrap",
            GAME_ID,
            "--",
            "sh",
            "-c",
            f"printf 'after' > {working / 'save.dat'}",
        ],
    )

    assert result.exit_code == 0

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "after"


def test_cli_wrap_without_a_command_explains_itself(registered_game):

    result = runner.invoke(app, ["wrap", GAME_ID])

    assert result.exit_code == 2
    assert "%command%" in result.output


def test_cli_wrap_rejects_an_unregistered_game():

    result = runner.invoke(app, ["wrap", "nonexistent", "--", "true"])

    assert result.exit_code == 1
    assert "not registered" in result.output


def test_cli_wrap_passes_the_exit_code_through(registered_game):

    result = runner.invoke(app, ["wrap", GAME_ID, "--", "false"])

    assert result.exit_code == 1


def test_cli_wrap_reports_a_missing_binary(registered_game):

    result = runner.invoke(
        app,
        ["wrap", GAME_ID, "--", "definitely-not-a-real-binary"],
    )

    assert result.exit_code == 127
    assert "Could not run" in result.output


def test_cli_wrap_forwards_game_options(tmp_path):
    """
    Steam's %command% carries options that belong to the game, not to
    SaveCloud, so they must not be parsed as SaveCloud's own.
    """

    working = tmp_path / "working"

    write_save(working, "before")

    register_game(working)

    marker = tmp_path / "argv.txt"

    result = runner.invoke(
        app,
        [
            "wrap",
            GAME_ID,
            "--",
            "sh",
            "-c",
            f'printf "%s" "$*" > {marker}',
            "sh",
            "--fullscreen",
            "-w",
            "1920",
        ],
    )

    assert result.exit_code == 0

    assert marker.read_text(encoding="utf-8") == "--fullscreen -w 1920"


def test_cli_wrap_reports_a_conflict(registered_game, working_save):

    SyncService.sync(registered_game)

    write_save(working_save, "local progress")

    advance_remote(GAME_ID, "remote progress")

    result = runner.invoke(app, ["wrap", GAME_ID, "--", "true"])

    assert result.exit_code == 1
    assert "--keep-local" in result.output
    assert "not launched" in result.output


def test_cli_wrap_rejects_options_after_the_game_id(registered_game):
    """
    Parsing stops at the game ID, so a later option would silently
    become part of the game's command line.
    """

    result = runner.invoke(
        app,
        ["wrap", GAME_ID, "--keep-local", "--", "true"],
    )

    assert result.exit_code == 2
    assert "must come before the game ID" in result.output


def test_cli_wrap_resolves_a_conflict_when_told(registered_game, working_save):

    SyncService.sync(registered_game)

    write_save(working_save, "local progress")

    advance_remote(GAME_ID, "remote progress")

    result = runner.invoke(
        app,
        ["wrap", "--keep-local", GAME_ID, "--", "true"],
    )

    assert result.exit_code == 0

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "local progress"


def test_cli_play_points_at_wrap_for_steam(registered_game, device_id):
    """
    Refusing is correct, but the user needs the alternative.
    """

    profile = DeviceService.load_profile(device_id, GAME_ID)

    profile.launcher = "steam"
    profile.launch_command = "2050650"

    DeviceService.save_profile(profile)

    result = runner.invoke(app, ["play", GAME_ID])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert f"savecloud wrap {GAME_ID} -- %command%" in result.output


def test_doctor_explains_how_to_launch_a_steam_game(registered_game, device_id):

    from savecloud.services.diagnostics import DiagnosticsService

    profile = DeviceService.load_profile(device_id, GAME_ID)

    profile.launcher = "steam"
    profile.launch_command = "2050650"

    DeviceService.save_profile(profile)

    findings = DiagnosticsService.run()

    launch = [f for f in findings if f.title == "Launch through Steam"]

    assert launch, [f.title for f in findings]
    assert f"savecloud wrap {GAME_ID} -- %command%" in (launch[0].remedy or "")
