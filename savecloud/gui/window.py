"""
The main window.

Actions run on worker threads and report through the status bar. While
one is running the controls are disabled, so a second sync cannot be
started on top of the first - the services are not written to expect
two callers at once, and the interface is the only thing that can
prevent it.

Anything that discards a save asks first.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from savecloud.gui import worker
from savecloud.gui.dialogs import (
    ACCEPTED,
    GameSettingsDialog,
    PairDialog,
    RegisterDialog,
    SettingsDialog,
)
from savecloud.gui.facade import GameRow, GuiFacade

#
# Status values that deserve to be visible at a glance in the list.
#

ATTENTION = {"conflict", "error", "pending"}

#
# How long to let background work finish when closing. Long enough for
# a probe that is nearly done, short enough that a hung network never
# holds the window open.
#

WORKER_SHUTDOWN_MS = 3000


def _side(summary, fallback: str) -> str:
    """
    Name one side of a conflict for a button.

    A button reading "Keep Steam Deck" says which save is being kept;
    "Keep the remote save" only says where it happens to live.
    """

    if summary is None:
        return fallback

    where = summary.where

    return "this device" if where == "This device" else where


class GameList(QWidget):
    """
    Every registered game, with its state.
    """

    def __init__(self) -> None:

        super().__init__()

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        self.list = QListWidget()

        layout.addWidget(self.list)

    def show_games(self, games: list[GameRow]) -> None:
        """
        Replace the contents with a fresh reading.
        """

        self.list.clear()

        if not games:

            placeholder = QListWidgetItem("No games are registered yet.")

            placeholder.setFlags(Qt.NoItemFlags)

            self.list.addItem(placeholder)

            return

        for game in games:

            item = QListWidgetItem(f"{game.display_name}\n{game.summary}")

            item.setData(Qt.UserRole, game.game_id)

            if game.status in ATTENTION or not game.paired:
                font = item.font()

                font.setBold(True)

                item.setFont(font)

            self.list.addItem(item)

    def selected(self) -> str | None:
        """
        The game the user is looking at, if any.
        """

        item = self.list.currentItem()

        return None if item is None else item.data(Qt.UserRole)

    def select(self, game_id: str | None) -> None:
        """
        Select a game by ID, if it is still listed.
        """

        if game_id is None:
            return

        for index in range(self.list.count()):

            if self.list.item(index).data(Qt.UserRole) == game_id:
                self.list.setCurrentRow(index)

                return


class DetailPane(QTextEdit):
    """
    Everything known about one game.
    """

    def __init__(self) -> None:

        super().__init__()

        self.setReadOnly(True)

        self.show_nothing()

    def show_nothing(self) -> None:

        self.setPlainText("Select a game.")

    def show_error(self, message: str) -> None:

        self.setPlainText(message)

    def show_detail(self, detail) -> None:
        """
        Render one game's state as plain text.
        """

        lines = [
            detail.display_name,
            detail.game_id,
            "",
            f"Platform         {detail.platform}",
            f"Adapter          {detail.adapter}",
            "",
            f"Status           {detail.status}",
            f"Automatic sync   {'on' if detail.auto_sync else 'off'}",
            f"Latest version   {detail.latest_version}",
            f"Last sync        {detail.last_sync}",
            f"Last device      {detail.last_device}",
        ]

        if detail.restored_from:
            lines.append(f"Restored from    version {detail.restored_from}")

        if detail.pending_upload:
            lines += ["", "This device has changes waiting to upload."]

        if detail.last_error:
            lines += ["", f"Last error       {detail.last_error}"]

        if not detail.paired:
            lines += [
                "",
                "This game is not set up on this device.",
                f"Adopt it with:  savecloud pair {detail.game_id}",
            ]

        else:
            lines += [
                "",
                f"Launcher         {detail.launcher}",
                f"Working save     {detail.working_save_path}",
                f"Launch command   {detail.launch_command or '(none - launched by Steam)'}",
                "",
                "Steam launch options",
                f"  {GuiFacade.steam_launch_options(detail.game_id)}",
            ]

        lines += ["", f"Versions kept    {len(detail.versions)}"]

        if detail.versions:
            lines.append("  " + ", ".join(str(v) for v in detail.versions))

        self.setPlainText("\n".join(lines))


class HealthPane(QTextEdit):
    """
    What `doctor` would say.
    """

    MARKERS = {"ok": "✓", "warning": "!", "error": "✗"}

    def __init__(self) -> None:

        super().__init__()

        self.setReadOnly(True)

        self.setPlainText("Not checked yet.")

    def show_findings(self, findings) -> None:

        problems = [finding for finding in findings if finding.is_problem]

        if not problems:

            self.setPlainText(
                f"No problems found.\n\n{len(findings)} checks passed."
            )

            return

        blocks = []

        for finding in problems:

            marker = self.MARKERS.get(finding.severity, "-")

            block = [f"{marker} {finding.title}"]

            if finding.detail:
                block.append(f"    {finding.detail}")

            if finding.remedy:
                block.append(f"    → {finding.remedy}")

            blocks.append("\n".join(block))

        self.setPlainText("\n\n".join(blocks))


class MainWindow(QMainWindow):
    """
    SaveCloud's desktop window.
    """

    def __init__(self, facade: type[GuiFacade] = GuiFacade) -> None:

        super().__init__()

        self.facade = facade

        self.setWindowTitle("SaveCloud")

        self.resize(900, 560)

        self._build()

        self.refresh()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:

        central = QWidget()

        layout = QVBoxLayout(central)

        #
        # Built before the layouts, since a layout that references a
        # button has to have one.
        #

        self.add_button = QPushButton("Add game…")

        self.add_button.clicked.connect(self._register)

        self.pair_button = QPushButton("Pair…")

        self.pair_button.clicked.connect(self._pair)

        self.settings_button = QPushButton("Settings…")

        self.settings_button.clicked.connect(self._settings)

        self.game_settings_button = QPushButton("Edit…")

        self.game_settings_button.clicked.connect(self._game_settings)

        self.remove_button = QPushButton("Remove…")

        self.remove_button.clicked.connect(self._unregister)

        #
        # Header: which machine this is, and where saves go.
        #

        header = QHBoxLayout()

        self.device_label = QLabel()

        self.storage_label = QLabel()

        self.refresh_button = QPushButton("Refresh")

        self.refresh_button.clicked.connect(self.refresh)

        header.addWidget(self.device_label)

        header.addStretch()

        header.addWidget(self.storage_label)

        header.addWidget(self.settings_button)

        header.addWidget(self.refresh_button)

        layout.addLayout(header)

        library = QHBoxLayout()

        library.addWidget(self.add_button)

        library.addWidget(self.pair_button)

        library.addWidget(self.game_settings_button)

        library.addWidget(self.remove_button)

        library.addStretch()

        layout.addLayout(library)

        #
        # Body: games on the left, whatever is selected on the right.
        #

        self.games = GameList()

        self.games.list.currentItemChanged.connect(self._selection_changed)

        self.detail = DetailPane()

        self.health = HealthPane()

        self.tabs = QTabWidget()

        self.tabs.addTab(self.detail, "Game")

        self.tabs.addTab(self.health, "Health")

        splitter = QSplitter()

        splitter.addWidget(self.games)

        splitter.addWidget(self.tabs)

        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

        layout.addLayout(self._build_actions())

        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())

    def _build_actions(self):
        """
        The row of things a person can do to the selected game.
        """

        row = QHBoxLayout()

        self.play_button = QPushButton("Play")

        self.play_button.clicked.connect(self._play)

        self.sync_button = QPushButton("Sync")

        self.sync_button.clicked.connect(self._sync)

        self.sync_all_button = QPushButton("Sync all")

        self.sync_all_button.clicked.connect(self._sync_all)

        self.snapshot_button = QPushButton("Snapshot")

        self.snapshot_button.clicked.connect(self._snapshot)

        self.restore_button = QPushButton("Restore…")

        self.restore_button.clicked.connect(self._restore)

        self.auto_sync_box = QCheckBox("Sync automatically on this device")

        self.auto_sync_box.clicked.connect(self._auto_sync_toggled)

        row.addWidget(self.play_button)

        row.addWidget(self.sync_button)

        row.addWidget(self.snapshot_button)

        row.addWidget(self.restore_button)

        row.addWidget(self.auto_sync_box)

        row.addStretch()

        row.addWidget(self.sync_all_button)

        #
        # Everything acting on a selection starts disabled: there is no
        # selection yet.
        #

        self._per_game = [
            self.play_button,
            self.sync_button,
            self.snapshot_button,
            self.restore_button,
            self.auto_sync_box,
        ]

        #
        # Editing and removing apply to a selection too, but stay
        # usable for a game not set up on this device: editing is how
        # a wrong save path gets corrected, and removing is how a game
        # nobody wants here goes away.
        #

        self._per_selection = [
            self.game_settings_button,
            self.remove_button,
        ]

        for control in self._per_selection:
            control.setEnabled(False)

        for control in self._per_game:
            control.setEnabled(False)

        return row

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _busy(self, doing: str) -> None:
        """
        Disable the controls and say what is happening.

        The services are not written to expect two callers at once, and
        this is the only thing that can stop a second sync starting on
        top of the first.
        """

        self._working = True

        for control in self._per_game + self._per_selection + [
            self.sync_all_button,
            self.refresh_button,
            self.add_button,
            self.pair_button,
            self.settings_button,
        ]:
            control.setEnabled(False)

        self.statusBar().showMessage(doing)

    def _done(self, outcome) -> None:
        """
        Re-enable, report, and re-read.
        """

        self._working = False

        self.refresh()

        if outcome.conflict:
            self._resolve_conflict(outcome)

            return

        #
        # Conflicts found while synchronizing everything. Each is the
        # same question a single sync asks, so each is asked the same
        # way rather than reported as a failure with nothing to press.
        #

        if outcome.conflicts:
            self._resolve_conflicts(outcome)

            return

        if not outcome.ok:
            QMessageBox.warning(self, "SaveCloud", outcome.message)

            self.statusBar().showMessage(outcome.message.split("\n")[0], 8000)

            return

        self.statusBar().showMessage(outcome.message, 8000)

    def _failed(self, message: str) -> None:
        """
        A worker raised despite the facade catching what it could.
        """

        self._working = False

        self.refresh()

        QMessageBox.critical(self, "SaveCloud", message)

    def _run(self, work, doing: str) -> None:
        """
        Start background work, with the controls locked meanwhile.
        """

        if getattr(self, "_working", False):
            return

        self._busy(doing)

        worker.run(
            work,
            on_result=self._done,
            on_error=self._failed,
            on_progress=lambda message: self.statusBar().showMessage(message),
        )

    def _play(self) -> None:

        game_id = self.games.selected()

        if game_id is None:
            return

        self._run(
            lambda: self.facade.play(game_id),
            f"Launching {game_id}…",
        )

    def _sync(self, resolution: str = "abort") -> None:

        game_id = self.games.selected()

        if game_id is None:
            return

        self._run(
            lambda: self.facade.sync(game_id, resolution),
            f"Synchronizing {game_id}…",
        )

    def _sync_all(self) -> None:

        self._run(self.facade.sync_all, "Synchronizing every game…")

    def _snapshot(self) -> None:

        game_id = self.games.selected()

        if game_id is None:
            return

        self._run(
            lambda: self.facade.snapshot(game_id),
            f"Capturing {game_id}…",
        )

    def _restore(self) -> None:
        """
        Restore a version, after asking which one and confirming.
        """

        game_id = self.games.selected()

        if game_id is None:
            return

        try:
            detail = self.facade.detail(game_id)

        except KeyError:
            return

        if not detail.versions:
            QMessageBox.information(
                self,
                "SaveCloud",
                "This game has no saved versions yet.",
            )

            return

        labels = [str(version) for version in detail.versions]

        chosen, accepted = QInputDialog.getItem(
            self,
            "Restore a version",
            "Version to restore:",
            labels,
            len(labels) - 1,
            False,
        )

        if not accepted:
            return

        #
        # Restoring replaces the current save. It is reversible - what
        # it replaces becomes a new version - but it is still the kind
        # of thing to be asked about rather than told.
        #

        confirmed = QMessageBox.question(
            self,
            "Restore a version",
            f"Replace the current save for {detail.display_name} with "
            f"version {chosen}?\n\nThe save being replaced is kept as a "
            f"new version, so this can be undone.",
        )

        if confirmed is not QMessageBox.Yes:
            return

        self._run(
            lambda: self.facade.restore(game_id, int(chosen)),
            f"Restoring version {chosen}…",
        )

    def _auto_sync_toggled(self, checked: bool) -> None:

        game_id = self.games.selected()

        if game_id is None:
            return

        self._run(
            lambda: self.facade.set_auto_sync(game_id, checked),
            "Saving…",
        )

    # ------------------------------------------------------------------
    # Library and configuration
    # ------------------------------------------------------------------

    def _register(self) -> None:
        """
        Add a game to this device.
        """

        dialog = RegisterDialog(self.facade)

        if dialog.exec() != ACCEPTED:
            return

        self.refresh()

        self.games.select(dialog.outcome.game_id)

        self.statusBar().showMessage(dialog.outcome.message, 8000)

        self._offer_launch_options(dialog.outcome.game_id)

    def _offer_launch_options(self, game_id: str) -> None:
        """
        Hand over the line Steam needs, at the moment it is needed.

        Registering a game is exactly when someone is about to go and
        add it to Steam, and the alternative is finding this in a
        detail pane they have no reason to read yet.
        """

        options = self.facade.steam_launch_options(game_id)

        box = QMessageBox(self)

        box.setWindowTitle("Add to Steam")

        box.setText(
            "Put this in the game's Launch Options in Steam, and "
            "SaveCloud will synchronize around every session:"
        )

        box.setInformativeText(options)

        copy = box.addButton("Copy", QMessageBox.ActionRole)

        box.addButton("Close", QMessageBox.RejectRole)

        box.exec()

        if box.clickedButton() is copy:

            QApplication.clipboard().setText(options)

            self.statusBar().showMessage("Copied to the clipboard.", 5000)

    def _pair(self) -> None:
        """
        Adopt a game storage already holds.
        """

        available = self.facade.pairable()

        if not available.ok:
            QMessageBox.warning(self, "SaveCloud", available.message)

            return

        games = [line for line in available.message.split("\n") if line]

        if not games:
            QMessageBox.information(
                self,
                "SaveCloud",
                "Storage holds no games this device has not already "
                "adopted.",
            )

            return

        dialog = PairDialog(games, self.facade)

        if dialog.exec() != ACCEPTED:
            return

        self.refresh()

        self.games.select(dialog.outcome.game_id)

        self.statusBar().showMessage(dialog.outcome.message, 8000)

        self._offer_launch_options(dialog.outcome.game_id)

    def _game_settings(self) -> None:
        """
        Edit the selected game.
        """

        game_id = self.games.selected()

        if game_id is None:
            return

        try:
            detail = self.facade.detail(game_id)

        except KeyError:
            return

        dialog = GameSettingsDialog(detail, self.facade)

        if dialog.exec() != ACCEPTED:
            return

        self.refresh()

        self.games.select(game_id)

        self.statusBar().showMessage("Saved.", 5000)

    def _unregister(self) -> None:
        """
        Remove the selected game from this device.
        """

        game_id = self.games.selected()

        if game_id is None:
            return

        try:
            detail = self.facade.detail(game_id)

        except KeyError:
            return

        #
        # This deletes the library, which is where versions live. The
        # confirmation says so, because "remove" sounds reversible and
        # this is the one action here that is not.
        #

        confirmed = QMessageBox.question(
            self,
            "Remove a game",
            f"Remove {detail.display_name} from this device?\n\n"
            f"Its saves and {len(detail.versions)} versions are deleted "
            f"here. Anything already in storage stays there.",
        )

        if confirmed is not QMessageBox.Yes:
            return

        outcome = self.facade.unregister(game_id)

        self.refresh()

        if not outcome.ok:
            QMessageBox.warning(self, "SaveCloud", outcome.message)

            return

        self.statusBar().showMessage(outcome.message, 8000)

    def _settings(self) -> None:
        """
        Change where saves go and how much history is kept.
        """

        dialog = SettingsDialog(self.facade)

        if dialog.exec() != ACCEPTED:
            return

        self.refresh()

        QMessageBox.information(self, "SaveCloud", dialog.outcome.message)

    def _ask_conflict(self, game_id: str, local, remote) -> str | None:
        """
        Ask which side to keep, and return the answer.

        The one dialog the whole design exists to make possible: both
        sides hold real play time, and only the person who played knows
        which matters. Whichever loses is kept as a version, which is
        what makes offering the choice safe rather than final.

        Returns "keep-local", "keep-remote", or None for deciding
        later.
        """

        box = QMessageBox(self)

        box.setWindowTitle("Both sides changed")

        box.setText(
            f"{game_id} has changed on this device and in "
            f"storage since they last agreed."
        )

        #
        # The descriptions are the point of the dialog. "Keep this one
        # or that one" with nothing else said is a coin toss over
        # someone's progress; when each was written, and on what, is
        # what makes it a decision.
        #

        details = [
            summary.description
            for summary in (local, remote)
            if summary is not None
        ]

        box.setInformativeText(
            "\n".join(details)
            + ("\n\n" if details else "")
            + "Whichever save you do not keep is saved to this game's "
            "version history, so nothing is lost either way."
        )

        keep_local = box.addButton(
            f"Keep {_side(local, 'this device')}",
            QMessageBox.AcceptRole,
        )

        keep_remote = box.addButton(
            f"Keep {_side(remote, 'the remote')}",
            QMessageBox.DestructiveRole,
        )

        box.addButton("Decide later", QMessageBox.RejectRole)

        box.exec()

        clicked = box.clickedButton()

        if clicked is keep_local:
            return "keep-local"

        if clicked is keep_remote:
            return "keep-remote"

        return None

    def _resolve_conflict(self, outcome) -> None:
        """
        Ask about one conflict, and act on the answer.
        """

        choice = self._ask_conflict(
            outcome.game_id,
            outcome.local,
            outcome.remote,
        )

        if choice is None:
            return

        #
        # Named rather than taken from the selection. The dialog is
        # modal but the list is rebuilt by the refresh that precedes
        # it, and resolving whichever game happens to be selected
        # afterwards is not what was asked.
        #

        game_id = outcome.game_id

        self._run(
            lambda: self.facade.sync(game_id, choice),
            f"Resolving {game_id}…",
        )

    def _resolve_conflicts(self, outcome) -> None:
        """
        Ask about every conflict a whole-library sync turned up.

        All the questions first, then one wait. Someone shown three
        conflicts answers three times; making them wait for a transfer
        between each would be a worse way to ask the same thing.
        """

        decisions = {}

        for conflict in outcome.conflicts:

            choice = self._ask_conflict(
                conflict.game_id,
                conflict.local,
                conflict.remote,
            )

            if choice is not None:
                decisions[conflict.game_id] = choice

        #
        # Anything that failed for a reason other than a conflict still
        # has to be reported; declining every conflict leaves that as
        # the only thing worth saying.
        #

        if not decisions:

            if not outcome.ok and outcome.message:
                self.statusBar().showMessage(
                    outcome.message.split("\n")[0],
                    8000,
                )

            return

        self._run(
            lambda: self.facade.resolve_conflicts(decisions),
            f"Resolving {len(decisions)}…",
        )

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """
        Re-read everything.

        The game list is local and fast, so it is read directly. The
        backend probe is a network call and goes to a thread.
        """

        self.device_label.setText(f"Device: {self.facade.device_name()}")

        #
        # Rebuilding the list drops the selection, so it is put back:
        # every action refreshes, and losing the selected game each
        # time would make the buttons unusable.
        #

        selected = self.games.selected()

        self.games.show_games(self.facade.games())

        self.games.select(selected)

        self.storage_label.setText("Storage: checking…")

        self.refresh_button.setEnabled(False)

        working = getattr(self, "_working", False)

        for control in (
            self.sync_all_button,
            self.add_button,
            self.pair_button,
            self.settings_button,
        ):
            control.setEnabled(not working)

        worker.run(
            self.facade.storage,
            on_result=self._storage_read,
            on_error=self._storage_failed,
        )

        worker.run(
            self.facade.diagnostics,
            on_result=self.health.show_findings,
            on_error=lambda message: self.health.setPlainText(message),
        )

    def _storage_read(self, summary) -> None:

        self.refresh_button.setEnabled(not getattr(self, "_working", False))

        if summary.available:
            self.storage_label.setText(f"Storage: {summary.display_name}")

            self.statusBar().showMessage(summary.root, 5000)

            return

        self.storage_label.setText(f"Storage: {summary.display_name} unavailable")

        self.statusBar().showMessage(summary.reason)

    def _storage_failed(self, message: str) -> None:

        self.refresh_button.setEnabled(not getattr(self, "_working", False))

        self.storage_label.setText("Storage: unavailable")

        self.statusBar().showMessage(message)

    def closeEvent(self, event) -> None:
        """
        Let running work finish before the window goes away.

        A worker holds signals connected to widgets. Tearing the window
        down while one is still running leaves those signals pointing
        at objects Qt has deleted, which surfaces as warnings now and
        would be a crash on a slower probe.
        """

        worker.wait(WORKER_SHUTDOWN_MS)

        super().closeEvent(event)

    def _selection_changed(self, *_) -> None:

        game_id = self.games.selected()

        if game_id is None:
            self.detail.show_nothing()

            for control in self._per_game + self._per_selection:
                control.setEnabled(False)

            return

        try:
            detail = self.facade.detail(game_id)

        except KeyError:
            self.detail.show_error(f'"{game_id}" is no longer registered.')

            for control in self._per_game + self._per_selection:
                control.setEnabled(False)

            return

        self.detail.show_detail(detail)

        if getattr(self, "_working", False):
            return

        for control in self._per_game + self._per_selection:
            control.setEnabled(True)

        #
        # A game with no profile here cannot be played, captured, or
        # restored: nothing knows where its save lives on this machine.
        # Editing and removing stay available - editing is how the
        # missing details get supplied.
        #

        if not detail.paired:
            for control in self._per_game:
                control.setEnabled(False)

        self.auto_sync_box.blockSignals(True)

        self.auto_sync_box.setChecked(detail.auto_sync)

        self.auto_sync_box.setEnabled(detail.paired)

        self.auto_sync_box.blockSignals(False)
