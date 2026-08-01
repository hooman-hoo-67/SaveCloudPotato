"""
Tests for the desktop interface.

Widgets are driven headlessly. The point is not that Qt works, but
that the facade answers correctly and the window renders what it is
given without reaching into a service to do it.
"""

from __future__ import annotations

import pytest

from savecloud.services.registry import RegistryService
from savecloud.services.save import SaveService
from savecloud.services.sync import SyncService

from tests.conftest import GAME_ID, register_game, write_save

facade_module = pytest.importorskip(
    "savecloud.gui.facade",
    exc_type=ImportError,
)

GuiFacade = facade_module.GuiFacade


#
# Facade
#


def test_games_are_listed_with_their_state(registered_game):

    rows = GuiFacade.games()

    assert [row.game_id for row in rows] == [GAME_ID]

    assert rows[0].paired is True

    assert rows[0].auto_sync is True


def test_games_are_sorted_by_display_name(tmp_path):

    for name, game_id in (("Zelda", "z"), ("Animal Crossing", "a")):

        working = tmp_path / game_id

        write_save(working, "contents")

        register_game(working, game_id=game_id)

        game = RegistryService.load_game(game_id)

        RegistryService.create_registry(game)

    rows = GuiFacade.games()

    assert [row.game_id for row in rows] == sorted(row.game_id for row in rows)


def test_an_unpaired_game_says_so(registered_game):

    from savecloud.services.device import DeviceService
    from savecloud.services.library import SaveCloudLibrary

    DeviceService.delete_profile(SaveCloudLibrary.device_id(), GAME_ID)

    row = GuiFacade.games()[0]

    assert row.paired is False

    assert "not set up" in row.summary


def test_a_pending_upload_outranks_the_status(registered_game):

    game = RegistryService.load_game(GAME_ID)

    game.runtime.mark_pending()

    RegistryService.update_runtime(game)

    assert GuiFacade.games()[0].summary == "waiting to upload"


def test_detail_reports_the_latest_version_not_the_runtime_copy(
    registered_game,
    working_save,
):
    """
    The runtime's current_version is written at registration and never
    updated, so it reads 0 forever. The library owns save data.
    """

    write_save(working_save, "progress")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    detail = GuiFacade.detail(GAME_ID)

    assert detail.latest_version == len(detail.versions)

    assert detail.latest_version > 0

    assert RegistryService.load_runtime(GAME_ID).current_version == 0


def test_detail_reports_a_restore(registered_game, working_save):

    for index in range(3):
        write_save(working_save, f"session {index}")

        SyncService.sync(RegistryService.load_game(GAME_ID))

    versions = SaveService.list_versions(RegistryService.load_game(GAME_ID))

    SaveService.restore_version(RegistryService.load_game(GAME_ID), versions[0])

    assert GuiFacade.detail(GAME_ID).restored_from == versions[0]


def test_detail_names_this_device_rather_than_a_uuid(
    registered_game,
    working_save,
):

    write_save(working_save, "progress")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    assert GuiFacade.detail(GAME_ID).last_device == "this device"


def test_detail_rejects_an_unregistered_game(registered_game):

    with pytest.raises(KeyError):
        GuiFacade.detail("never-registered")


def test_storage_reports_the_backend(registered_game):

    summary = GuiFacade.storage()

    assert summary.backend == "local"

    assert summary.available is True

    assert summary.reason == ""


def test_storage_reports_an_unknown_backend_without_raising(registered_game):

    from savecloud.models.installation_config import InstallationConfig
    from savecloud.services.configuration import ConfigurationService

    ConfigurationService.save(
        InstallationConfig(storage_backend="nonexistent-provider")
    )

    summary = GuiFacade.storage()

    assert summary.available is False

    assert "not a known backend" in summary.reason


def test_diagnostics_are_flattened_for_display(registered_game):

    findings = GuiFacade.diagnostics()

    assert findings

    for finding in findings:
        assert finding.severity in {"ok", "warning", "error"}

        assert isinstance(finding.detail, str)


#
# Window
#


@pytest.fixture
def qt_app(monkeypatch):
    """
    A Qt application, rendered offscreen.
    """

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    QtWidgets = pytest.importorskip(
        "PySide6.QtWidgets",
        exc_type=ImportError,
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    yield app

    #
    # Workers hold signals connected to widgets the test is about to
    # drop. Draining the pool keeps one test's background work from
    # firing into the next test's objects.
    #

    from savecloud.gui import worker

    worker.wait()

    app.processEvents()


def test_the_window_lists_games(qt_app, registered_game):

    from savecloud.gui.window import MainWindow

    window = MainWindow()

    assert window.games.list.count() == 1

    window.games.list.setCurrentRow(0)

    assert GAME_ID in window.detail.toPlainText()


def test_the_window_says_when_nothing_is_registered(qt_app):

    from savecloud.gui.window import MainWindow

    window = MainWindow()

    assert "No games" in window.games.list.item(0).text()


def test_the_placeholder_cannot_be_selected(qt_app):
    """
    Selecting it would ask the facade for a game called "No games...".
    """

    from PySide6.QtCore import Qt
    from savecloud.gui.window import MainWindow

    window = MainWindow()

    assert window.games.list.item(0).flags() == Qt.NoItemFlags


def test_the_window_renders_an_unregistered_selection_as_a_message(
    qt_app,
    registered_game,
):
    """
    A game can disappear between listing and selecting it.
    """

    from savecloud.gui.window import MainWindow

    window = MainWindow()

    window.games.list.setCurrentRow(0)

    RegistryService.delete_registry(GAME_ID)

    window._selection_changed()

    assert "no longer registered" in window.detail.toPlainText()


def test_health_renders_a_clean_installation(qt_app, registered_game):

    from savecloud.gui.window import MainWindow

    window = MainWindow()

    window.health.show_findings(GuiFacade.diagnostics())

    assert "No problems found" in window.health.toPlainText()


def test_health_renders_problems_with_their_remedy(qt_app):

    from savecloud.gui.facade import Finding
    from savecloud.gui.window import MainWindow

    window = MainWindow()

    window.health.show_findings(
        [
            Finding(
                severity="error",
                title="Storage backend",
                detail="It is not reachable.",
                remedy="Run: savecloud config validate",
            )
        ]
    )

    rendered = window.health.toPlainText()

    assert "✗ Storage backend" in rendered

    assert "→ Run: savecloud config validate" in rendered


#
# Actions
#
# Every one returns an Outcome rather than raising: a window cannot
# catch an exception thrown on a worker thread.
#


def test_sync_reports_what_it_did(registered_game, working_save):

    write_save(working_save, "progress")

    outcome = GuiFacade.sync(GAME_ID)

    assert outcome.ok is True

    assert outcome.action == "upload"


def test_sync_reports_a_conflict_as_a_question(registered_game, working_save):
    """
    Not an error. The interface has to offer a choice.
    """

    from tests.test_sync import advance_remote

    GuiFacade.sync(GAME_ID)

    advance_remote(GAME_ID, "remote progress")

    write_save(working_save, "local progress")

    outcome = GuiFacade.sync(GAME_ID)

    assert outcome.ok is False

    assert outcome.conflict is True


def test_a_conflict_can_be_resolved_either_way(registered_game, working_save):

    from savecloud.storage import LocalStorageBackend
    from tests.conftest import read_save
    from tests.test_sync import advance_remote

    GuiFacade.sync(GAME_ID)

    advance_remote(GAME_ID, "remote progress")

    write_save(working_save, "local progress")

    assert GuiFacade.sync(GAME_ID, "keep-local").ok is True

    assert read_save(
        LocalStorageBackend.current_directory(GAME_ID)
    ) == "local progress"


def test_the_losing_side_of_a_conflict_is_kept(registered_game, working_save):
    """
    What makes offering the choice safe rather than final.
    """

    from tests.test_sync import advance_remote

    GuiFacade.sync(GAME_ID)

    before = len(GuiFacade.detail(GAME_ID).versions)

    advance_remote(GAME_ID, "remote progress")

    write_save(working_save, "local progress")

    GuiFacade.sync(GAME_ID, "keep-local")

    assert len(GuiFacade.detail(GAME_ID).versions) > before


def test_an_unregistered_game_fails_without_raising(registered_game):

    outcome = GuiFacade.sync("never-registered")

    assert outcome.ok is False

    assert outcome.conflict is False


def test_unreachable_storage_fails_without_raising(registered_game, monkeypatch):

    from savecloud.storage import LocalStorageBackend

    monkeypatch.setattr(
        LocalStorageBackend,
        "available",
        classmethod(lambda cls: False),
    )

    outcome = GuiFacade.sync(GAME_ID)

    assert outcome.ok is False

    assert outcome.conflict is False


def test_snapshot_creates_a_version(registered_game, working_save):

    write_save(working_save, "progress")

    before = len(GuiFacade.detail(GAME_ID).versions)

    assert GuiFacade.snapshot(GAME_ID).ok is True

    assert len(GuiFacade.detail(GAME_ID).versions) == before + 1


def test_restore_reports_that_it_is_reversible(registered_game, working_save):

    for index in range(3):
        write_save(working_save, f"session {index}")

        GuiFacade.sync(GAME_ID)

    versions = GuiFacade.detail(GAME_ID).versions

    outcome = GuiFacade.restore(GAME_ID, versions[0])

    assert outcome.ok is True

    assert "kept as a new version" in outcome.message


def test_auto_sync_can_be_turned_off_and_on(registered_game):

    assert GuiFacade.set_auto_sync(GAME_ID, False).ok is True

    assert GuiFacade.detail(GAME_ID).auto_sync is False

    assert GuiFacade.set_auto_sync(GAME_ID, True).ok is True

    assert GuiFacade.detail(GAME_ID).auto_sync is True


def test_auto_sync_refuses_an_unpaired_game(registered_game):

    from savecloud.services.device import DeviceService
    from savecloud.services.library import SaveCloudLibrary

    DeviceService.delete_profile(SaveCloudLibrary.device_id(), GAME_ID)

    outcome = GuiFacade.set_auto_sync(GAME_ID, False)

    assert outcome.ok is False

    assert "not set up" in outcome.message


def test_sync_all_reports_a_count(registered_game, working_save):

    write_save(working_save, "progress")

    outcome = GuiFacade.sync_all()

    assert outcome.ok is True

    assert "1 games" in outcome.message


#
# The window's action wiring
#


def test_buttons_are_disabled_until_a_game_is_selected(qt_app, registered_game):

    from savecloud.gui.window import MainWindow

    window = MainWindow()

    assert window.sync_button.isEnabled() is False

    window.games.list.setCurrentRow(0)

    assert window.sync_button.isEnabled() is True


def test_buttons_are_disabled_for_an_unpaired_game(qt_app, registered_game):
    """
    Nothing knows where the save lives here, so nothing can act on it.
    """

    from savecloud.services.device import DeviceService
    from savecloud.services.library import SaveCloudLibrary
    from savecloud.gui.window import MainWindow

    DeviceService.delete_profile(SaveCloudLibrary.device_id(), GAME_ID)

    window = MainWindow()

    window.games.list.setCurrentRow(0)

    assert window.play_button.isEnabled() is False

    assert window.auto_sync_box.isEnabled() is False


def test_an_action_locks_the_controls_while_it_runs(qt_app, registered_game):
    """
    The services expect one caller. This is the only thing that can
    stop a second sync starting on top of the first.
    """

    from savecloud.gui.window import MainWindow

    window = MainWindow()

    window.games.list.setCurrentRow(0)

    window._sync()

    assert window.sync_button.isEnabled() is False

    assert window.sync_all_button.isEnabled() is False


def test_a_second_action_is_refused_while_one_runs(qt_app, registered_game):

    from savecloud.gui.window import MainWindow

    window = MainWindow()

    window.games.list.setCurrentRow(0)

    window._working = True

    started = []

    window._run(lambda: started.append(1), "doing")

    assert started == []


def test_the_selection_survives_a_refresh(qt_app, registered_game):
    """
    Every action refreshes, and losing the selection each time would
    make the buttons unusable.
    """

    from savecloud.gui.window import MainWindow

    window = MainWindow()

    window.games.list.setCurrentRow(0)

    window.refresh()

    assert window.games.selected() == GAME_ID


def test_the_checkbox_reflects_the_stored_setting(qt_app, registered_game):

    from savecloud.gui.window import MainWindow

    GuiFacade.set_auto_sync(GAME_ID, False)

    window = MainWindow()

    window.games.list.setCurrentRow(0)

    assert window.auto_sync_box.isChecked() is False


def test_setting_the_checkbox_does_not_re_fire_on_refresh(
    qt_app,
    registered_game,
    monkeypatch,
):
    """
    Refreshing sets the checkbox from stored state. If that emitted,
    the interface would write back what it had just read - and an
    action would run on every selection change.
    """

    from savecloud.gui.window import MainWindow

    window = MainWindow()

    calls = []

    monkeypatch.setattr(
        window,
        "_run",
        lambda work, doing: calls.append(doing),
    )

    window.games.list.setCurrentRow(0)

    window.refresh()

    assert calls == []
