"""
Tests for the interface's forms.

A form that closes and then complains has thrown away what the person
typed, so the ones here check that a refusal keeps the dialog open with
its input intact - not only that the happy path works.
"""

from __future__ import annotations

import pytest

from savecloud.services.registry import RegistryService

from tests.conftest import GAME_ID, write_save

pytest.importorskip("PySide6.QtWidgets")

from savecloud.gui.facade import GuiFacade  # noqa: E402


@pytest.fixture
def qt_app():

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    yield app

    from savecloud.gui import worker

    worker.wait()

    app.processEvents()


@pytest.fixture
def save_folder(tmp_path):

    folder = tmp_path / "working"

    write_save(folder, "contents")

    return str(folder)


#
# Registering
#


def test_a_game_id_is_suggested_from_the_display_name(qt_app):

    from savecloud.gui.dialogs import RegisterDialog

    dialog = RegisterDialog()

    dialog.display_name.setText("Breath of the Wild")

    assert dialog.game_id.text() == "breath-of-the-wild"


def test_the_suggestion_stops_once_the_id_is_edited(qt_app):
    """
    A suggestion that overwrites what someone typed is not a
    suggestion.
    """

    from savecloud.gui.dialogs import RegisterDialog

    dialog = RegisterDialog()

    dialog.display_name.setText("Zelda")

    dialog.game_id.setText("botw")

    dialog._stop_suggesting()

    dialog.display_name.setText("Zelda: Breath of the Wild")

    assert dialog.game_id.text() == "botw"


def test_the_identifier_label_follows_the_adapter(qt_app):

    from savecloud.gui.dialogs import RegisterDialog

    dialog = RegisterDialog()

    assert dialog.identifier_label.text() == "Save Folder"

    dialog.adapter.setCurrentText("steam-proton")

    assert dialog.identifier_label.text() == "Steam App ID"


def test_the_default_adapter_takes_a_folder(qt_app):
    """
    Whichever sorted first would otherwise win, and reading a folder
    path as a Title ID fails in a way that blames the person.
    """

    from savecloud.gui.dialogs import RegisterDialog

    assert RegisterDialog().adapter.currentText() == "manual"


def test_registering_creates_the_game(qt_app, save_folder):

    from savecloud.gui.dialogs import ACCEPTED, RegisterDialog

    dialog = RegisterDialog()

    dialog.display_name.setText("Breath of the Wild")

    dialog.identifier.setText(save_folder)

    dialog.launch_command.setText("true")

    dialog.submit()

    assert dialog.result() == ACCEPTED

    assert RegistryService.exists("breath-of-the-wild")


def test_a_refused_registration_keeps_the_form_open(qt_app, save_folder):

    from savecloud.gui.dialogs import ACCEPTED, RegisterDialog

    def fill(dialog):
        dialog.display_name.setText("Breath of the Wild")
        dialog.identifier.setText(save_folder)
        dialog.launch_command.setText("true")

    first = RegisterDialog()

    fill(first)

    first.submit()

    second = RegisterDialog()

    fill(second)

    second.submit()

    assert second.result() != ACCEPTED

    assert "already registered" in second.message.text()

    #
    # And what was typed is still there to correct.
    #

    assert second.display_name.text() == "Breath of the Wild"


def test_a_missing_save_folder_is_refused(qt_app):

    from savecloud.gui.dialogs import ACCEPTED, RegisterDialog

    dialog = RegisterDialog()

    dialog.display_name.setText("Nowhere")

    dialog.identifier.setText("/definitely/not/here")

    dialog.launch_command.setText("true")

    dialog.submit()

    assert dialog.result() != ACCEPTED

    assert "No save directory" in dialog.message.text()


def test_a_missing_launch_command_is_refused(qt_app, save_folder):

    from savecloud.gui.dialogs import ACCEPTED, RegisterDialog

    dialog = RegisterDialog()

    dialog.display_name.setText("Nameless")

    dialog.identifier.setText(save_folder)

    dialog.submit()

    assert dialog.result() != ACCEPTED

    assert "Launch command" in dialog.message.text()


#
# Editing
#


def test_editing_changes_both_halves(qt_app, registered_game, save_folder):

    from savecloud.gui.dialogs import GameSettingsDialog

    dialog = GameSettingsDialog(GuiFacade.detail(GAME_ID))

    dialog.display_name.setText("Renamed")

    dialog.working_save_path.setText(save_folder)

    dialog.launch_command.setText("echo played")

    dialog.submit()

    detail = GuiFacade.detail(GAME_ID)

    assert detail.display_name == "Renamed"

    assert detail.launch_command == "echo played"


def test_editing_refuses_a_path_that_is_not_a_directory(
    qt_app,
    registered_game,
):

    from savecloud.gui.dialogs import ACCEPTED, GameSettingsDialog

    dialog = GameSettingsDialog(GuiFacade.detail(GAME_ID))

    dialog.working_save_path.setText("/definitely/not/here")

    dialog.submit()

    assert dialog.result() != ACCEPTED

    assert "not a directory" in dialog.message.text()


def test_editing_an_unpaired_game_offers_only_the_shared_half(
    qt_app,
    registered_game,
):

    from savecloud.services.device import DeviceService
    from savecloud.services.library import SaveCloudLibrary
    from savecloud.gui.dialogs import GameSettingsDialog

    DeviceService.delete_profile(SaveCloudLibrary.device_id(), GAME_ID)

    dialog = GameSettingsDialog(GuiFacade.detail(GAME_ID))

    assert dialog.working_save_path.isEnabled() is False

    assert dialog.display_name.isEnabled() is True


#
# Settings
#


def test_settings_show_the_current_configuration(qt_app, registered_game):

    from savecloud.gui.dialogs import SettingsDialog

    dialog = SettingsDialog()

    assert dialog.backend.currentData() == "local"

    assert dialog.retention.value() == GuiFacade.settings().retention


def test_saving_settings_applies_retention(qt_app, registered_game, working_save):
    """
    Matching `config retention`: a window that took effect at some
    later moment would read as one that did nothing.
    """

    from savecloud.services.sync import SyncService
    from savecloud.gui.dialogs import SettingsDialog

    GuiFacade.save_settings("local", GuiFacade.settings().root, 0)

    for index in range(5):
        write_save(working_save, f"session {index}")

        SyncService.sync(RegistryService.load_game(GAME_ID))

    assert len(GuiFacade.detail(GAME_ID).versions) == 5

    dialog = SettingsDialog()

    dialog.retention.setValue(2)

    dialog.submit()

    assert len(GuiFacade.detail(GAME_ID).versions) == 2


def test_the_credentials_button_appears_only_when_needed(qt_app):

    from savecloud.gui.dialogs import SettingsDialog

    dialog = SettingsDialog()

    dialog.backend.setCurrentIndex(dialog.backend.findData("dropbox"))

    assert dialog._needs_setup["dropbox"] is True

    assert dialog._needs_setup["local"] is False


def test_an_unknown_backend_is_refused_without_losing_the_form(qt_app):

    from savecloud.gui.dialogs import ACCEPTED, SettingsDialog

    dialog = SettingsDialog()

    dialog.backend.addItem("Nonexistent", "nonexistent-provider")

    dialog.backend.setCurrentIndex(
        dialog.backend.findData("nonexistent-provider")
    )

    dialog.submit()

    assert dialog.result() != ACCEPTED

    assert dialog.message.text()


#
# Dropbox setup
#


def test_dropbox_setup_needs_an_app_key_before_authorizing(qt_app):

    from savecloud.gui.dialogs import DropboxSetupDialog

    dialog = DropboxSetupDialog()

    dialog._authorize()

    assert "App key is required" in dialog.message.text()


def test_dropbox_setup_refuses_empty_fields(qt_app):

    from savecloud.gui.dialogs import ACCEPTED, DropboxSetupDialog

    dialog = DropboxSetupDialog()

    dialog.submit()

    assert dialog.result() != ACCEPTED

    assert "required" in dialog.message.text()


def test_dropbox_setup_stores_a_refresh_token(qt_app, monkeypatch):

    from savecloud.services.credentials import CredentialService
    from savecloud.storage import dropbox_setup
    from savecloud.gui.dialogs import ACCEPTED, DropboxSetupDialog

    monkeypatch.setattr(
        dropbox_setup,
        "exchange_code",
        lambda key, secret, code: {"refresh_token": "a-refresh-token"},
    )

    dialog = DropboxSetupDialog()

    dialog.app_key.setText("key")

    dialog.app_secret.setText("secret")

    dialog.code.setText("code")

    dialog.submit()

    assert dialog.result() == ACCEPTED

    assert CredentialService.load("dropbox")["refresh_token"] == "a-refresh-token"


def test_dropbox_setup_explains_a_reused_code(qt_app, monkeypatch):
    """
    The most common way this fails, and the least obvious.
    """

    from savecloud.storage import dropbox_setup
    from savecloud.gui.dialogs import ACCEPTED, DropboxSetupDialog

    monkeypatch.setattr(
        dropbox_setup,
        "exchange_code",
        lambda key, secret, code: {},
    )

    dialog = DropboxSetupDialog()

    dialog.app_key.setText("key")

    dialog.app_secret.setText("secret")

    dialog.code.setText("used-already")

    dialog.submit()

    assert dialog.result() != ACCEPTED

    assert "works once" in dialog.message.text()


#
# Removing
#


def test_unregistering_removes_the_game(registered_game):

    assert GuiFacade.unregister(GAME_ID).ok is True

    assert RegistryService.exists(GAME_ID) is False

    assert GuiFacade.games() == []


#
# Hidden directories
#
# Emulator saves live under ~/.local/share, and every component after
# the home directory is hidden. A picker that cannot show dotfiles
# cannot reach a single Linux save.
#


def _picker(parent=None):
    """
    Build the directory picker the Browse button uses.
    """

    from PySide6.QtCore import QDir
    from PySide6.QtWidgets import QFileDialog

    dialog = QFileDialog(parent, "Select a folder")

    dialog.setFileMode(QFileDialog.FileMode.Directory)

    dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)

    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)

    dialog.setFilter(dialog.filter() | QDir.Filter.Hidden)

    return dialog


def test_the_picker_lists_hidden_directories(qt_app, tmp_path):

    from PySide6.QtCore import QDir

    (tmp_path / ".local").mkdir()

    (tmp_path / "Documents").mkdir()

    dialog = _picker()

    dialog.setDirectory(str(tmp_path))

    listed = set(
        dialog.directory().entryList(
            dialog.filter() | QDir.Filter.NoDotAndDotDot
        )
    )

    assert ".local" in listed

    assert "Documents" in listed


def test_the_default_picker_would_not_have(qt_app, tmp_path):
    """
    The convenience function offers no way to change this, which is
    why the dialog is built by hand.
    """

    from PySide6.QtCore import QDir
    from PySide6.QtWidgets import QFileDialog

    dialog = QFileDialog()

    dialog.setFileMode(QFileDialog.FileMode.Directory)

    assert not bool(dialog.filter() & QDir.Filter.Hidden)


def test_a_game_can_be_registered_at_a_hidden_path(qt_app, tmp_path):
    """
    The real shape of an Eden save location.
    """

    from savecloud.gui.dialogs import ACCEPTED, RegisterDialog

    save = (
        tmp_path
        / ".local/share/eden/nand/user/save/0000000000000000"
        / "1194B8A5A401B4CE44808A6B1DBF10B2/0100F43008C44000"
    )

    save.mkdir(parents=True)

    (save / "save.dat").write_text("contents")

    dialog = RegisterDialog()

    dialog.display_name.setText("Breath of the Wild")

    dialog.identifier.setText(str(save))

    dialog.launch_command.setText("true")

    dialog.submit()

    assert dialog.result() == ACCEPTED

    assert GuiFacade.detail("breath-of-the-wild").working_save_path == str(save)


def test_a_home_relative_path_is_expanded(qt_app, tmp_path, monkeypatch):
    """
    Typing ~/... has to work, since that is how these paths are
    written down and pasted.
    """

    monkeypatch.setenv("HOME", str(tmp_path))

    save = tmp_path / ".local/share/eden/saves"

    save.mkdir(parents=True)

    outcome = GuiFacade.locate_save("manual", "~/.local/share/eden/saves")

    assert outcome.ok is True

    assert outcome.value == str(save)
