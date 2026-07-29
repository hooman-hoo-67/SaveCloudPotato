"""
Forms.

Each collects input, validates through the facade, and reports what
went wrong in the dialog rather than behind it - a form that closes and
then complains has thrown away what the person typed.

Registering and pairing both do real work (locating a save, downloading
a library), so they run it on the interface thread deliberately: a
modal dialog is already blocking, and the alternative is a dialog that
must stay alive across a thread boundary to receive its own result.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDir
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from savecloud.gui.facade import GuiFacade

#
# PySide6 exposes this on the enum, not on an instance, and the
# instance form fails only at the moment a dialog closes - which is
# the least convenient time to discover it.
#

ACCEPTED = QDialog.DialogCode.Accepted


class _Form(QDialog):
    """
    Shared behaviour: a form, a message line, and OK/Cancel.
    """

    def __init__(self, title: str, facade=GuiFacade) -> None:

        super().__init__()

        self.facade = facade

        self.setWindowTitle(title)

        self.setMinimumWidth(520)

        self.form = QFormLayout()

        self.message = QLabel()

        self.message.setWordWrap(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )

        self.buttons.accepted.connect(self.submit)

        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)

        layout.addLayout(self.form)

        layout.addWidget(self.message)

        layout.addWidget(self.buttons)

    def complain(self, message: str) -> None:
        """
        Report a problem without closing.
        """

        self.message.setText(message)

    def submit(self) -> None:
        """
        Validate and, if it holds, accept.
        """

        outcome = self.attempt()

        #
        # Recorded either way. A caller that wants to know why a form
        # refused should not have to read the label.
        #

        self.outcome = outcome

        if outcome is None or outcome.ok:
            self.accept()

            return

        self.complain(outcome.message)

    def attempt(self):
        """
        Do the work. Return an Outcome, or None to accept regardless.
        """

        raise NotImplementedError


def _directory_row(
    field: QLineEdit,
    parent: QWidget,
    start_in=None,
) -> QWidget:
    """
    A text field with a Browse button beside it.

    ``start_in`` is called for a directory to open at when the field is
    empty - which is how browsing for a Proton save starts inside the
    game's prefix rather than in the home directory, several levels and
    one hidden folder away.
    """

    row = QWidget(parent)

    layout = QHBoxLayout(row)

    layout.setContentsMargins(0, 0, 0, 0)

    button = QPushButton("Browse…")

    def browse() -> None:
        """
        Pick a directory, hidden ones included.

        Emulator saves live under `~/.local/share`, and every part of
        that path after the home directory is hidden. A picker that
        cannot show dotfiles cannot reach a single Linux save, so this
        builds the dialog rather than using the convenience function -
        which offers no way to change the filter.

        Qt's own dialog is used rather than the desktop's, because the
        native one keeps its own notion of hidden files that this
        cannot set.
        """

        dialog = QFileDialog(parent, "Select a folder")

        dialog.setFileMode(QFileDialog.FileMode.Directory)

        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)

        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)

        dialog.setFilter(dialog.filter() | QDir.Filter.Hidden)

        #
        # Start where the field points, so correcting a path does not
        # mean navigating back to it from the home directory.
        #

        current = field.text().strip()

        if not current and start_in is not None:
            current = start_in() or ""

        if current:

            start = Path(current).expanduser()

            if not start.is_dir():
                start = start.parent

            if start.is_dir():
                dialog.setDirectory(str(start))

        if dialog.exec() != ACCEPTED:
            return

        chosen = dialog.selectedFiles()

        if chosen:
            field.setText(chosen[0])

    button.clicked.connect(browse)

    layout.addWidget(field)

    layout.addWidget(button)

    #
    # Kept reachable so a form whose field stops being a path can hide
    # it. Offering to browse for a Title ID sends people looking
    # through their filesystem for a number.
    #

    row.browse_button = button

    return row


def _browse_into(
    setter,
    parent: QWidget,
    current,
    start_in=None,
) -> QPushButton:
    """
    A Browse button that writes the chosen directory back.

    Separate from `_directory_row` because a combo box owns its own
    line edit: moving that into another layout takes it out of the
    combo box, which then shows nothing.
    """

    button = QPushButton("Browse…")

    def browse() -> None:

        dialog = QFileDialog(parent, "Select a folder")

        dialog.setFileMode(QFileDialog.FileMode.Directory)

        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)

        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)

        dialog.setFilter(dialog.filter() | QDir.Filter.Hidden)

        start = (current() or "").strip()

        if not start and start_in is not None:
            start = start_in() or ""

        if start:

            path = Path(start).expanduser()

            if not path.is_dir():
                path = path.parent

            if path.is_dir():
                dialog.setDirectory(str(path))

        if dialog.exec() != ACCEPTED:
            return

        chosen = dialog.selectedFiles()

        if chosen:
            setter(chosen[0])

    button.clicked.connect(browse)

    return button


class RegisterDialog(_Form):
    """
    Register a game on this device.
    """

    def __init__(self, facade=GuiFacade) -> None:

        super().__init__("Register a game", facade)

        options = facade.options()

        self.display_name = QLineEdit()

        self.game_id = QLineEdit()

        self.launch_type = QComboBox()

        self.launch_type.addItems(options.launch_types)

        self.platform = QComboBox()

        self.platform.addItems(options.platforms)

        self.adapter = QComboBox()

        self._adapters = {choice.name: choice for choice in options.adapters}

        self.adapter.addItems([choice.name for choice in options.adapters])

        #
        # Whichever sorted first would otherwise win, and reading a
        # folder path as a Title ID fails in a way that blames the
        # person rather than the default.
        #

        if "manual" in self._adapters:
            self.adapter.setCurrentText("manual")

        self.adapter.currentTextChanged.connect(self._adapter_changed)

        self.identifier = QLineEdit()

        self.launcher = QComboBox()

        self.launcher.addItems(options.launchers)

        self.launch_command = QLineEdit()

        self.form.addRow("Display name", self.display_name)

        self.form.addRow("Game ID", self.game_id)

        self.form.addRow("Launch type", self.launch_type)

        self.form.addRow("Platform", self.platform)

        self.form.addRow("Adapter", self.adapter)

        self.identifier_label = QLabel()

        self.identifier_row = _directory_row(
            self.identifier,
            self,
            start_in=self._prefix_root,
        )

        self.form.addRow(self.identifier_label, self.identifier_row)

        #
        # Proton asks two questions instead of one: which game, and
        # where inside its prefix the save lives. A Windows game
        # follows no convention, so the second cannot be inferred.
        #

        self.steam_game = QComboBox()

        self._steam_games = facade.steam_games()

        for game in self._steam_games:
            self.steam_game.addItem(game.label, game.app_id)

        if not self._steam_games:
            self.steam_game.addItem("No Steam games found", "")

        self.steam_game.currentIndexChanged.connect(self._steam_game_changed)

        self.steam_game_label = QLabel("Steam game")

        self.form.addRow(self.steam_game_label, self.steam_game)

        #
        # Editable, so a guess can be chosen from the list or a path
        # typed or browsed for. One control, three ways in.
        #

        self.save_folder = QComboBox()

        self.save_folder.setEditable(True)

        self.save_folder_label = QLabel("Save folder")

        self.save_folder_row = QWidget(self)

        save_layout = QHBoxLayout(self.save_folder_row)

        save_layout.setContentsMargins(0, 0, 0, 0)

        self.save_folder_browse = _browse_into(
            self.save_folder.setCurrentText,
            self,
            self.save_folder.currentText,
            start_in=self._prefix_root,
        )

        save_layout.addWidget(self.save_folder, 1)

        save_layout.addWidget(self.save_folder_browse)

        self.form.addRow(self.save_folder_label, self.save_folder_row)

        self.form.addRow("Launcher", self.launcher)

        self.launch_command.setPlaceholderText(
            "optional - only needed for savecloud play"
        )

        self.form.addRow("Launch command", self.launch_command)

        self.message.setText(
            "A game launched from Steam does not need a launch command. "
            "SaveCloud gives you a line to paste into its Launch "
            "Options once it is registered."
        )

        #
        # A game ID nobody typed is worse than one derived from the
        # name, so it is suggested until it is edited by hand.
        #

        self.display_name.textChanged.connect(self._suggest_game_id)

        self.game_id.textEdited.connect(self._stop_suggesting)

        self._suggesting = True

        self._adapter_changed(self.adapter.currentText())

    def _adapter_changed(self, adapter: str) -> None:
        """
        Ask for what this adapter actually wants.
        """

        proton = adapter == "steam-proton"

        for widget in (
            self.steam_game,
            self.steam_game_label,
            self.save_folder_label,
            self.save_folder_row,
        ):
            widget.setVisible(proton)

        for widget in (self.identifier, self.identifier_label,
                       self.identifier_row):
            widget.setVisible(not proton)

        if proton:
            self._steam_game_changed()

            return

        choice = self._adapters.get(adapter)

        if choice is None:
            self.identifier_label.setText("Identifier")

            return

        self.identifier_label.setText(choice.identifier_name)

        self.identifier_row.browse_button.setVisible(
            choice.identifier_is_path
        )

        self.identifier.setPlaceholderText(
            "" if choice.identifier_is_path else choice.identifier_name
        )

    def _selected_app_id(self) -> str:
        """
        The Steam game currently chosen, if any.
        """

        return self.steam_game.currentData() or ""

    def _prefix_root(self) -> str:
        """
        Where browsing for this game's save should start.
        """

        app_id = self._selected_app_id()

        return self.facade.prefix_root(app_id) if app_id else ""

    def _steam_game_changed(self, *_) -> None:
        """
        Offer whatever looks like a save directory in this prefix.

        Reported rather than chosen between: Windows games follow no
        convention, and silently synchronizing the wrong directory is
        worse than one more question.
        """

        app_id = self._selected_app_id()

        self.save_folder.clear()

        if not app_id:
            self.message.setText("No installed Steam games were found.")

            return

        if not self.facade.prefix_root(app_id):
            self.message.setText(
                "That game has no Proton prefix yet. Launch it once "
                "through Steam, then reopen this window."
            )

            return

        candidates = self.facade.save_candidates(app_id)

        self.save_folder.addItems(candidates)

        self.save_folder.setCurrentText(candidates[0] if candidates else "")

        self.message.setText(
            f"{len(candidates)} folder(s) in this prefix look like saves. "
            f"Pick one, or browse for it - Windows games follow no "
            f"convention, so this is a guess."
            if candidates
            else "Nothing in this prefix looks like a save yet. Play the "
            "game once so it writes one, then browse for it."
        )

    def _suggest_game_id(self, name: str) -> None:

        if not self._suggesting:
            return

        suggestion = "".join(
            character if character.isalnum() else "-"
            for character in name.strip().lower()
        )

        while "--" in suggestion:
            suggestion = suggestion.replace("--", "-")

        self.game_id.setText(suggestion.strip("-"))

    def _stop_suggesting(self, *_) -> None:

        self._suggesting = False

    def attempt(self):

        adapter = self.adapter.currentText()

        if adapter == "steam-proton":

            built = self.facade.steam_identifier(
                self._selected_app_id(),
                self.save_folder.currentText(),
            )

            if not built.ok:
                return built

            identifier = built.value

        else:
            identifier = self.identifier.text()

        return self.facade.register(
            game_id=self.game_id.text(),
            display_name=self.display_name.text(),
            launch_type=self.launch_type.currentText(),
            platform=self.platform.currentText(),
            adapter=adapter,
            identifier=identifier,
            launcher=self.launcher.currentText(),
            launch_command=self.launch_command.text(),
        )


class PairDialog(_Form):
    """
    Adopt a game that already exists in storage.
    """

    def __init__(self, available: list[str], facade=GuiFacade) -> None:

        super().__init__("Pair a game", facade)

        options = facade.options()

        self.game = QComboBox()

        self.game.addItems(available)

        self.game.currentTextChanged.connect(self._game_changed)

        self.identifier = QLineEdit()

        self.launcher = QComboBox()

        self.launcher.addItems(options.launchers)

        self.launch_command = QLineEdit()

        self.launch_command.setPlaceholderText(
            "optional - only needed for savecloud play"
        )

        self.form.addRow("Game in storage", self.game)

        self.identifier_label = QLabel("Save location")

        self.identifier_row = _directory_row(self.identifier, self)

        self.form.addRow(self.identifier_label, self.identifier_row)

        self.form.addRow("Launcher", self.launcher)

        self.form.addRow("Launch command", self.launch_command)

        self.message.setText(
            "The game's configuration comes from storage. Only what "
            "cannot be synchronized is asked for here."
        )

        self._game_changed(self.game.currentText())

    def _game_changed(self, game_id: str) -> None:
        """
        Ask for whatever this game's adapter needs.

        Which adapter that is arrives with the manifest, and the
        manifest arrives when the game is adopted - so until then this
        can only be specific about a game already known here. The
        field is labelled neutrally in the meantime, and corrected the
        moment adopting succeeds.
        """

        choice = self.facade.adapter_for(game_id)

        if choice is None:
            self.identifier_label.setText("Save location")

            self.identifier_row.browse_button.setVisible(True)

            self.identifier.setPlaceholderText("")

            return

        self.identifier_label.setText(choice.identifier_name)

        self.identifier_row.browse_button.setVisible(
            choice.identifier_is_path
        )

        self.identifier.setPlaceholderText(
            "" if choice.identifier_is_path else choice.identifier_name
        )

    def attempt(self):

        game_id = self.game.currentText()

        outcome = self.facade.pair(
            game_id=game_id,
            identifier=self.identifier.text(),
            launcher=self.launcher.currentText(),
            launch_command=self.launch_command.text(),
        )

        #
        # Adopting downloads the manifest, so after a first attempt the
        # adapter is known even if locating the save failed. Relabel
        # before the person tries again, rather than letting them fail
        # twice against a field asking the wrong question.
        #

        if not outcome.ok:
            self._game_changed(game_id)

        return outcome


class GameSettingsDialog(_Form):
    """
    Edit one game.

    Two groups, deliberately apart: what every device agrees on, and
    what belongs to this machine alone.
    """

    def __init__(self, detail, facade=GuiFacade) -> None:

        super().__init__(f"Settings for {detail.display_name}", facade)

        self.detail = detail

        options = facade.options()

        self.display_name = QLineEdit(detail.display_name)

        self.sync_enabled = QCheckBox("Manage this game on every device")

        self.sync_enabled.setChecked(True)

        self.backup_enabled = QCheckBox("Keep version history")

        self.backup_enabled.setChecked(True)

        self.form.addRow("Display name", self.display_name)

        self.form.addRow("", self.sync_enabled)

        self.form.addRow("", self.backup_enabled)

        self.working_save_path = QLineEdit(detail.working_save_path)

        self.launcher = QComboBox()

        self.launcher.addItems(options.launchers)

        if detail.launcher in options.launchers:
            self.launcher.setCurrentText(detail.launcher)

        self.launch_command = QLineEdit(detail.launch_command)

        self.form.addRow(QLabel("<b>This device only</b>"), QLabel(""))

        self.form.addRow(
            "Working save",
            _directory_row(self.working_save_path, self),
        )

        self.form.addRow("Launcher", self.launcher)

        self.launch_command.setPlaceholderText(
            "optional - only needed for savecloud play"
        )

        self.form.addRow("Launch command", self.launch_command)

        self.form.addRow("Steam launch options", self._launch_options_row())

        if not detail.paired:

            for widget in (
                self.working_save_path,
                self.launcher,
                self.launch_command,
            ):
                widget.setEnabled(False)

            self.message.setText("This game is not set up on this device.")

    def _launch_options_row(self) -> QWidget:
        """
        The line to paste into Steam, and a button that copies it.

        Read-only: it is derived from the game ID, so editing it would
        only produce a line that does not work.
        """

        row = QWidget(self)

        layout = QHBoxLayout(row)

        layout.setContentsMargins(0, 0, 0, 0)

        options = self.facade.steam_launch_options(self.detail.game_id)

        field = QLineEdit(options)

        field.setReadOnly(True)

        button = QPushButton("Copy")

        def copy() -> None:

            QApplication.clipboard().setText(options)

            self.complain("Copied to the clipboard.")

        button.clicked.connect(copy)

        layout.addWidget(field)

        layout.addWidget(button)

        self.launch_options_field = field

        self.copy_button = button

        return row

    def attempt(self):

        outcome = self.facade.update_game(
            self.detail.game_id,
            self.display_name.text(),
            self.sync_enabled.isChecked(),
            self.backup_enabled.isChecked(),
        )

        if not outcome.ok or not self.detail.paired:
            return outcome

        return self.facade.update_profile(
            self.detail.game_id,
            self.working_save_path.text(),
            self.launcher.currentText(),
            self.launch_command.text(),
        )


class SettingsDialog(_Form):
    """
    Where saves go, and how much history is kept.
    """

    def __init__(self, facade=GuiFacade) -> None:

        super().__init__("SaveCloud settings", facade)

        options = facade.options()

        settings = facade.settings()

        self.backend = QComboBox()

        self._needs_setup = {
            name: needs for name, _, needs in options.backends
        }

        for name, display, _ in options.backends:
            self.backend.addItem(display, name)

        index = self.backend.findData(settings.backend)

        if index >= 0:
            self.backend.setCurrentIndex(index)

        self.backend.currentIndexChanged.connect(self._backend_changed)

        self.root = QLineEdit(settings.root)

        self.retention = QSpinBox()

        self.retention.setRange(0, 999)

        self.retention.setValue(settings.retention)

        self.retention.setSpecialValueText("keep every version")

        self.credentials_button = QPushButton("Set up credentials…")

        self.credentials_button.clicked.connect(self._set_up_credentials)

        self.form.addRow("Storage", self.backend)

        self.form.addRow("Folder", _directory_row(self.root, self))

        self.form.addRow("Versions kept", self.retention)

        self.form.addRow("", self.credentials_button)

        #
        # Only shown for a downloaded build that is not yet reachable
        # by name. A pip installation already is.
        #

        self.install_button = QPushButton("Add to PATH and menu")

        self.install_button.clicked.connect(self._install)

        self.install_button.setVisible(facade.needs_installing())

        self.form.addRow("", self.install_button)

        self._backend_changed()

    def _selected_backend(self) -> str:

        return self.backend.currentData()

    def _backend_changed(self, *_) -> None:

        name = self._selected_backend()

        needs = self._needs_setup.get(name, False)

        self.credentials_button.setVisible(needs)

        if needs:
            self.message.setText(
                "For a cloud provider, Folder names a folder inside it "
                "rather than a path on this machine."
            )

        else:
            self.message.setText("")

    def _install(self) -> None:
        """
        Make `savecloud` reachable by name.
        """

        outcome = self.facade.install()

        self.complain(outcome.message)

        self.install_button.setVisible(self.facade.needs_installing())

    def _set_up_credentials(self) -> None:

        if self._selected_backend() != "dropbox":

            QMessageBox.information(
                self,
                "SaveCloud",
                "This backend has no credentials to set up.",
            )

            return

        DropboxSetupDialog(self.facade).exec()

    def attempt(self):

        return self.facade.save_settings(
            backend=self._selected_backend(),
            root=self.root.text(),
            retention=self.retention.value(),
        )


class DropboxSetupDialog(_Form):
    """
    Authorize SaveCloud with a Dropbox account.

    Three fields rather than a browser embedded in the window: Dropbox
    hands back a code to paste, and a real browser is one the person
    already trusts with their password.
    """

    def __init__(self, facade=GuiFacade) -> None:

        super().__init__("Set up Dropbox", facade)

        self.app_key = QLineEdit()

        self.app_secret = QLineEdit()

        self.app_secret.setEchoMode(QLineEdit.Password)

        self.code = QLineEdit()

        self.authorize_button = QPushButton("Open Dropbox to authorize")

        self.authorize_button.clicked.connect(self._authorize)

        self.form.addRow("App key", self.app_key)

        self.form.addRow("App secret", self.app_secret)

        self.form.addRow("", self.authorize_button)

        self.form.addRow("Authorization code", self.code)

        self.message.setText(
            "Create an app at dropbox.com/developers, then paste its "
            "key and secret above."
        )

    def _authorize(self) -> None:

        import webbrowser

        outcome = self.facade.dropbox_authorize_url(self.app_key.text())

        if not outcome.ok:
            self.complain(outcome.message)

            return

        webbrowser.open(outcome.value)

        self.complain(
            "Approve the request in your browser, then paste the code "
            "it shows into the field below. Each code works once."
        )

    def attempt(self):

        return self.facade.save_dropbox_credentials(
            self.app_key.text(),
            self.app_secret.text(),
            self.code.text(),
        )
