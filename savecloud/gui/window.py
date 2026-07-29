"""
The main window.

A read-only view: it shows what SaveCloud knows and never changes it.
Every button that would mutate a save is deliberately absent until the
plumbing beneath this - threading, progress, error rendering - has been
exercised on something that cannot destroy anything.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from savecloud.gui import worker
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
                f"Launch command   {detail.launch_command}",
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

        header.addWidget(self.refresh_button)

        layout.addLayout(header)

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

        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())

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

        self.games.show_games(self.facade.games())

        self.storage_label.setText("Storage: checking…")

        self.refresh_button.setEnabled(False)

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

        self.refresh_button.setEnabled(True)

        if summary.available:
            self.storage_label.setText(f"Storage: {summary.display_name}")

            self.statusBar().showMessage(summary.root, 5000)

            return

        self.storage_label.setText(f"Storage: {summary.display_name} unavailable")

        self.statusBar().showMessage(summary.reason)

    def _storage_failed(self, message: str) -> None:

        self.refresh_button.setEnabled(True)

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

            return

        try:
            self.detail.show_detail(self.facade.detail(game_id))

        except KeyError:
            self.detail.show_error(f'"{game_id}" is no longer registered.')
