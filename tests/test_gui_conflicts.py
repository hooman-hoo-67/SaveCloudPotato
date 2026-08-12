"""
Resolving a conflict without leaving the interface.

Both requests here came from using the thing: the authorization link
was opened and never shown, so a machine whose browser does not appear
had nothing to fall back on; and a conflict found by "Sync all" was
reported as a failure with no buttons, which left the command line as
the only way to answer a question two buttons wide.
"""

from __future__ import annotations

import pytest

from savecloud.models.save_summary import SaveSummary
from savecloud.services.sync import SyncConflictError

from tests.conftest import GAME_ID, register_game, write_save

#
# See tests/test_gui_forms.py for why exc_type is named.
#
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)

from savecloud.gui.facade import Conflict, GuiFacade  # noqa: E402


def conflict_error(game_id: str, local=None, remote=None) -> SyncConflictError:
    """
    The error the service really raises, checksums and all.
    """

    return SyncConflictError(
        game_id,
        local_checksum="aaa",
        remote_checksum="bbb",
        local=local,
        remote=remote,
    )


def summary(where: str, version: int) -> SaveSummary:

    return SaveSummary(
        where=where,
        modified="2026-08-01 12:00",
        age="10 minutes ago",
        version=version,
        checksum="abc123",
    )


#
# What a whole-library sync reports
#


def test_sync_all_offers_a_conflict_rather_than_reporting_it(
    monkeypatch,
    registered_game,
):
    """
    The complaint that prompted this: a conflict during "Sync all"
    arrived as a message box with nothing to press.
    """

    def conflicted(*_args, **_kwargs):
        return {
            GAME_ID: conflict_error(
                GAME_ID,
                local=summary("This device", 3),
                remote=summary("steamdeck", 7),
            )
        }

    monkeypatch.setattr(
        "savecloud.gui.facade.SyncService.sync_all",
        conflicted,
    )

    outcome = GuiFacade.sync_all()

    assert outcome.ok is False

    assert len(outcome.conflicts) == 1

    conflict = outcome.conflicts[0]

    assert conflict.game_id == GAME_ID

    #
    # Both sides described, which is what makes the choice a decision
    # rather than a coin toss.
    #

    assert conflict.local.version == 3
    assert conflict.remote.version == 7


def test_several_conflicts_are_all_offered(
    monkeypatch,
    working_save,
    tmp_path,
):

    other = tmp_path / "other-save"

    write_save(other, "other")

    register_game(other, game_id="second-game")

    def conflicted(*_args, **_kwargs):
        return {
            GAME_ID: conflict_error(GAME_ID),
            "second-game": conflict_error("second-game"),
        }

    monkeypatch.setattr(
        "savecloud.gui.facade.SyncService.sync_all",
        conflicted,
    )

    outcome = GuiFacade.sync_all()

    #
    # Sorted, so the questions come in the same order every time. A
    # dialog sequence that reshuffled between runs would be a poor way
    # to ask someone about their saves.
    #

    assert [conflict.game_id for conflict in outcome.conflicts] == [
        "second-game",
        GAME_ID,
    ]


def test_a_real_failure_is_still_reported(monkeypatch, registered_game):
    """
    A conflict is a question; a broken backend is not.
    """

    def mixed(*_args, **_kwargs):
        return {
            GAME_ID: conflict_error(GAME_ID),
            "broken": RuntimeError("storage is on fire"),
        }

    monkeypatch.setattr(
        "savecloud.gui.facade.SyncService.sync_all",
        mixed,
    )

    outcome = GuiFacade.sync_all()

    assert outcome.ok is False

    assert "storage is on fire" in outcome.message

    #
    # And the conflict still travels, so it can still be asked about.
    #

    assert len(outcome.conflicts) == 1


def test_a_clean_sync_carries_no_conflicts(registered_game):

    outcome = GuiFacade.sync_all()

    assert outcome.ok is True

    assert outcome.conflicts == []


#
# Applying the answers
#


def test_resolving_applies_each_decision(registered_game, working_save):

    GuiFacade.sync(GAME_ID)

    write_save(working_save, "local progress")

    outcome = GuiFacade.resolve_conflicts({GAME_ID: "keep-local"})

    assert outcome.ok is True

    assert "1 conflict" in outcome.message


def test_resolving_nothing_is_not_a_failure():

    outcome = GuiFacade.resolve_conflicts({})

    assert outcome.ok is True


def test_a_failed_resolution_is_reported(monkeypatch, registered_game):

    def broken(*_args, **_kwargs):
        raise RuntimeError("storage is unreachable")

    monkeypatch.setattr(
        "savecloud.gui.facade.SyncService.sync",
        broken,
    )

    outcome = GuiFacade.resolve_conflicts({GAME_ID: "keep-local"})

    assert outcome.ok is False

    assert "unreachable" in outcome.message


#
# The window
#


@pytest.fixture
def qt_app():

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    yield app

    from savecloud.gui import worker

    worker.wait()

    app.processEvents()


def test_the_window_asks_about_every_conflict(qt_app, monkeypatch, tmp_path):
    """
    Each conflict is its own question, so each is asked.
    """

    from savecloud.gui.window import MainWindow

    window = MainWindow()

    asked = []

    monkeypatch.setattr(
        MainWindow,
        "_ask_conflict",
        lambda self, game_id, local, remote: (
            asked.append(game_id) or "keep-local"
        ),
    )

    applied = {}

    monkeypatch.setattr(
        MainWindow,
        "_run",
        lambda self, work, doing: applied.update(decisions=work()),
    )

    window._resolve_conflicts(
        type(
            "Result",
            (),
            {
                "ok": False,
                "message": "",
                "conflicts": [
                    Conflict("first", summary("This device", 1), None),
                    Conflict("second", summary("This device", 2), None),
                ],
            },
        )()
    )

    assert asked == ["first", "second"]

    window.close()


def test_declining_every_conflict_changes_nothing(qt_app, monkeypatch):

    from savecloud.gui.window import MainWindow

    window = MainWindow()

    monkeypatch.setattr(
        MainWindow,
        "_ask_conflict",
        lambda self, game_id, local, remote: None,
    )

    ran = []

    monkeypatch.setattr(
        MainWindow,
        "_run",
        lambda self, work, doing: ran.append(doing),
    )

    window._resolve_conflicts(
        type(
            "Result",
            (),
            {
                "ok": False,
                "message": "",
                "conflicts": [Conflict("first", None, None)],
            },
        )()
    )

    assert ran == []

    window.close()


#
# The authorization link
#


def test_the_authorize_link_is_shown_not_only_opened(qt_app, monkeypatch):
    """
    `webbrowser.open` does nothing on a machine with no browser it can
    reach, and says so only by returning False. Someone there was left
    with a button that visibly did not work and no way round it.
    """

    import webbrowser

    from savecloud.gui.dialogs import DropboxSetupDialog

    monkeypatch.setattr(webbrowser, "open", lambda url: True)

    dialog = DropboxSetupDialog(GuiFacade)

    dialog.app_key.setText("an-app-key")

    dialog._authorize()

    link = dialog.authorize_link.text()

    assert link.startswith("https://www.dropbox.com/oauth2/authorize")

    assert "an-app-key" in link

    assert dialog.copy_button.isEnabled()

    dialog.close()


def test_a_missing_browser_still_leaves_the_link(qt_app, monkeypatch):

    import webbrowser

    from savecloud.gui.dialogs import DropboxSetupDialog

    monkeypatch.setattr(webbrowser, "open", lambda url: False)

    dialog = DropboxSetupDialog(GuiFacade)

    dialog.app_key.setText("an-app-key")

    dialog._authorize()

    assert dialog.authorize_link.text()

    assert "Copy the link" in dialog.message.text()

    dialog.close()


def test_a_browser_that_raises_is_not_a_failure(qt_app, monkeypatch):
    """
    A sandboxed build can raise rather than return False.
    """

    import webbrowser

    from savecloud.gui.dialogs import DropboxSetupDialog

    def explode(url):
        raise RuntimeError("no browser here")

    monkeypatch.setattr(webbrowser, "open", explode)

    dialog = DropboxSetupDialog(GuiFacade)

    dialog.app_key.setText("an-app-key")

    dialog._authorize()

    assert dialog.authorize_link.text()

    dialog.close()


def test_the_link_can_be_copied(qt_app, monkeypatch):

    import webbrowser

    from PySide6.QtWidgets import QApplication

    from savecloud.gui.dialogs import DropboxSetupDialog

    monkeypatch.setattr(webbrowser, "open", lambda url: True)

    dialog = DropboxSetupDialog(GuiFacade)

    dialog.app_key.setText("an-app-key")

    dialog._authorize()

    dialog._copy_link()

    assert QApplication.clipboard().text() == dialog.authorize_link.text()

    dialog.close()


def test_no_app_key_offers_no_link(qt_app):

    from savecloud.gui.dialogs import DropboxSetupDialog

    dialog = DropboxSetupDialog(GuiFacade)

    dialog._authorize()

    assert dialog.authorize_link.text() == ""

    assert not dialog.copy_button.isEnabled()

    dialog.close()
