"""
Tests for installation diagnostics.
"""

from __future__ import annotations

import shutil

import pytest

from savecloud.models.diagnostic import Severity
from savecloud.services.configuration import ConfigurationService
from savecloud.services.device import DeviceService
from savecloud.services.diagnostics import DiagnosticsService
from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.sync import SyncService
from savecloud.storage import SyncthingStorageBackend
from savecloud.storage.syncthing import FOLDER_MARKER

from tests.conftest import GAME_ID, build_game


def titles(findings) -> list[str]:
    """
    Return the titles of every finding.
    """

    return [finding.title for finding in findings]


def problems(findings) -> list:
    """
    Return only findings that represent something wrong.
    """

    return [finding for finding in findings if finding.is_problem]


def find(findings, title: str):
    """
    Return the first finding with a given title.
    """

    for finding in findings:
        if finding.title == title:
            return finding

    raise AssertionError(f"No finding titled {title!r} in {titles(findings)}")


#
# Healthy installation
#


def test_a_healthy_installation_reports_no_problems(registered_game):

    assert problems(DiagnosticsService.run()) == []


def test_a_healthy_installation_still_reports_what_it_checked(registered_game):

    findings = DiagnosticsService.run()

    assert "Installation" in titles(findings)
    assert "Storage backend" in titles(findings)

    assert all(finding.severity is Severity.OK for finding in findings)


def test_an_empty_installation_is_healthy():

    assert problems(DiagnosticsService.run()) == []


#
# Installation
#


def test_a_missing_installation_is_an_error(monkeypatch, tmp_path):

    monkeypatch.setenv("SAVECLOUD_HOME", str(tmp_path / "absent"))

    findings = DiagnosticsService.run()

    finding = find(findings, "Installation")

    assert finding.severity is Severity.ERROR
    assert "savecloud init" in (finding.remedy or "")


def test_a_broken_installation_stops_further_checks(monkeypatch, tmp_path):
    """
    Checking games against a missing installation would only add noise.
    """

    monkeypatch.setenv("SAVECLOUD_HOME", str(tmp_path / "absent"))

    findings = DiagnosticsService.run()

    assert len(findings) == 1


def test_a_partial_installation_is_an_error():

    shutil.rmtree(SaveCloudLibrary.library_directory("").parent)

    finding = find(DiagnosticsService.run(), "Installation")

    assert finding.severity is Severity.ERROR


#
# Storage backend
#


def test_an_unregistered_backend_is_an_error():

    from savecloud.models.installation_config import InstallationConfig

    ConfigurationService.save(
        InstallationConfig(storage_backend="dropbox"),
    )

    finding = find(DiagnosticsService.run(), "Storage backend")

    assert finding.severity is Severity.ERROR
    assert "dropbox" in finding.detail


def test_an_unavailable_backend_is_an_error():

    ConfigurationService.set_backend("syncthing")

    finding = find(DiagnosticsService.run(), "Storage backend")

    assert finding.severity is Severity.ERROR
    assert "Syncthing" in finding.detail


def test_an_unavailable_backend_says_saves_are_still_safe():

    ConfigurationService.set_backend("syncthing")

    finding = find(DiagnosticsService.run(), "Storage backend")

    assert "captured locally" in (finding.remedy or "")


def test_a_missing_config_file_is_a_warning():

    ConfigurationService.path().unlink()

    finding = find(DiagnosticsService.run(), "Configuration")

    assert finding.severity is Severity.WARNING


#
# Provider warnings
#


def test_syncthing_conflict_files_are_surfaced(storage_root):

    ConfigurationService.set_backend("syncthing")

    storage_root.mkdir(parents=True, exist_ok=True)

    (storage_root / FOLDER_MARKER).mkdir()

    game_directory = SyncthingStorageBackend.ensure_game_directory(GAME_ID)

    conflict = game_directory / "save.sync-conflict-20260101-120000-ABCDEFG.dat"

    conflict.write_text("other device", encoding="utf-8")

    finding = find(DiagnosticsService.run(), "Syncthing provider")

    assert finding.severity is Severity.WARNING
    assert "replication conflict" in finding.detail
    assert str(conflict) in finding.detail


def test_a_clean_syncthing_folder_produces_no_provider_warning(storage_root):

    ConfigurationService.set_backend("syncthing")

    storage_root.mkdir(parents=True, exist_ok=True)

    (storage_root / FOLDER_MARKER).mkdir()

    assert "Syncthing provider" not in titles(DiagnosticsService.run())


def test_the_local_backend_reports_no_provider_warnings(registered_game):

    from savecloud.storage import LocalStorageBackend

    assert LocalStorageBackend.provider_warnings() == []


def test_a_provider_that_raises_does_not_crash_diagnostics(monkeypatch):
    """
    Diagnostics runs against broken installations by definition.
    """

    from savecloud.storage import LocalStorageBackend

    def exploding():
        raise RuntimeError("provider is on fire")

    monkeypatch.setattr(
        LocalStorageBackend,
        "provider_warnings",
        staticmethod(exploding),
    )

    finding = find(DiagnosticsService.run(), "Local provider")

    assert finding.severity is Severity.WARNING
    assert "provider is on fire" in finding.detail


#
# Games
#


def test_a_missing_library_is_an_error():

    RegistryService.create_registry(build_game())

    finding = find(DiagnosticsService.run(), "Library missing")

    assert finding.severity is Severity.ERROR
    assert finding.game_id == GAME_ID


def test_a_game_without_a_local_profile_points_at_pair(registered_game, device_id):

    DeviceService.delete_profile(device_id, GAME_ID)

    finding = find(DiagnosticsService.run(), "Not set up on this device")

    assert finding.severity is Severity.WARNING
    assert f"savecloud pair {GAME_ID}" in (finding.remedy or "")


def test_a_missing_working_save_is_a_warning(registered_game, working_save):

    shutil.rmtree(working_save)

    finding = find(DiagnosticsService.run(), "Working save missing")

    assert finding.severity is Severity.WARNING


def test_an_unknown_adapter_is_an_error(registered_game):

    import json

    path = RegistryService.registry_manifest_path(GAME_ID)

    data = json.loads(path.read_text(encoding="utf-8"))

    data["adapter"] = "dolphin"

    path.write_text(json.dumps(data), encoding="utf-8")

    finding = find(DiagnosticsService.run(), "Unknown adapter")

    assert finding.severity is Severity.ERROR


def test_an_unknown_launcher_is_an_error(registered_game, device_id):

    profile = DeviceService.load_profile(device_id, GAME_ID)

    profile.launcher = "nonexistent"

    DeviceService.save_profile(profile)

    finding = find(DiagnosticsService.run(), "Unknown launcher")

    assert finding.severity is Severity.ERROR


def test_an_unrunnable_launch_command_is_only_a_warning(registered_game, device_id):
    """
    Synchronization does not depend on the launch command.
    """

    profile = DeviceService.load_profile(device_id, GAME_ID)

    profile.launch_command = "definitely-not-a-real-binary"

    DeviceService.save_profile(profile)

    finding = find(DiagnosticsService.run(), "Launch command will not run")

    assert finding.severity is Severity.WARNING


def test_an_unreadable_registry_is_reported(registered_game):

    RegistryService.registry_manifest_path(GAME_ID).write_text(
        "{ broken",
        encoding="utf-8",
    )

    finding = find(DiagnosticsService.run(), "Registry unreadable")

    assert finding.severity is Severity.ERROR


#
# Runtime state
#


def test_an_unresolved_conflict_is_surfaced(registered_game):

    registered_game.runtime.mark_conflict()

    RegistryService.update_runtime(registered_game)

    finding = find(DiagnosticsService.run(), "Unresolved conflict")

    assert finding.severity is Severity.WARNING
    assert "--keep-local" in (finding.remedy or "")


def test_a_pending_upload_is_surfaced(registered_game):

    registered_game.runtime.mark_pending()

    RegistryService.update_runtime(registered_game)

    finding = find(DiagnosticsService.run(), "Save waiting to upload")

    assert finding.severity is Severity.WARNING


def test_a_recorded_error_is_surfaced(registered_game):

    registered_game.runtime.mark_error("storage exploded")

    RegistryService.update_runtime(registered_game)

    finding = find(DiagnosticsService.run(), "Last operation failed")

    assert "storage exploded" in finding.detail


def test_a_game_stuck_running_is_surfaced(registered_game):
    """
    A session that ended without SaveCloud noticing was never captured.
    """

    registered_game.runtime.mark_running()

    RegistryService.update_runtime(registered_game)

    finding = find(DiagnosticsService.run(), "Marked as running")

    assert finding.severity is Severity.WARNING


def test_a_synced_game_produces_no_runtime_warning(registered_game):

    SyncService.sync(registered_game)

    assert problems(DiagnosticsService.run()) == []


#
# Orphans
#


def test_an_orphaned_library_is_surfaced(registered_game):

    RegistryService.delete_registry(GAME_ID)

    finding = find(DiagnosticsService.run(), "Orphaned library")

    assert finding.severity is Severity.WARNING

    #
    # The saves must not be deleted automatically.
    #

    assert SaveCloudLibrary.current_directory(GAME_ID).exists()


def test_an_orphaned_device_profile_is_surfaced(registered_game):

    RegistryService.delete_registry(GAME_ID)

    SaveCloudLibrary.delete_game_library(GAME_ID)

    finding = find(DiagnosticsService.run(), "Orphaned device profile")

    assert finding.severity is Severity.WARNING


#
# CLI
#


@pytest.fixture
def runner():
    from typer.testing import CliRunner

    return CliRunner()


def invoke(runner, *arguments):
    from savecloud.cli import app

    return runner.invoke(app, list(arguments))


def test_doctor_succeeds_on_a_healthy_installation(runner, registered_game):

    result = invoke(runner, "doctor")

    assert result.exit_code == 0
    assert "No problems found" in result.output


def test_doctor_verbose_lists_passing_checks(runner, registered_game):

    result = invoke(runner, "doctor", "--verbose")

    assert result.exit_code == 0
    assert "Installation" in result.output
    assert "Storage backend" in result.output


def test_doctor_exits_non_zero_on_errors(runner, registered_game):

    ConfigurationService.set_backend("syncthing")

    result = invoke(runner, "doctor")

    assert result.exit_code == 1
    assert "error" in result.output.lower()


def test_doctor_tolerates_warnings_by_default(runner, registered_game):

    registered_game.runtime.mark_pending()

    RegistryService.update_runtime(registered_game)

    result = invoke(runner, "doctor")

    assert result.exit_code == 0
    assert "Nothing is broken" in result.output


def test_doctor_strict_fails_on_warnings(runner, registered_game):

    registered_game.runtime.mark_pending()

    RegistryService.update_runtime(registered_game)

    result = invoke(runner, "doctor", "--strict")

    assert result.exit_code == 1


def test_doctor_shows_remedies(runner, registered_game):

    registered_game.runtime.mark_conflict()

    RegistryService.update_runtime(registered_game)

    result = invoke(runner, "doctor")

    assert "--keep-local" in result.output


def test_doctor_reports_an_uninitialized_installation(runner, monkeypatch, tmp_path):

    monkeypatch.setenv("SAVECLOUD_HOME", str(tmp_path / "absent"))

    result = invoke(runner, "doctor")

    assert result.exit_code == 1
    assert "savecloud init" in result.output
