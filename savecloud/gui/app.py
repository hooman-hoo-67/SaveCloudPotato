"""
Entry point for the desktop interface.
"""

from __future__ import annotations

import sys


def main() -> int:
    """
    Start the interface.

    PySide6 is imported here rather than at module scope so the CLI
    keeps working on a machine that has no Qt installed.
    """

    try:
        from PySide6.QtWidgets import QApplication

    except ImportError:
        sys.stderr.write(
            "The desktop interface needs PySide6:\n"
            "    pip install savecloud[gui]\n"
        )

        return 1

    from savecloud.gui.window import MainWindow

    app = QApplication(sys.argv)

    app.setApplicationName("SaveCloud")

    window = MainWindow()

    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
