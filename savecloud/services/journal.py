"""
A record of what SaveCloud did.

`savecloud wrap` runs inside Steam. There is no terminal, so every
warning it prints goes somewhere nobody will ever read - which is how a
failed upload during a Gaming Mode session looks exactly like a
successful one. `doctor` reports the state of an installation now, and
never what happened during a session that cannot be reproduced.

So the interesting moments are written down: what synchronization
decided, what a session did, and every failure with its reason.

Named `journal` rather than `logging` because the standard library owns
that name and shadowing it inside a package that also imports it is a
trap for whoever reads this next.

Nothing here may raise. A log is a convenience; a save is not. Failing
to write a line must never be the reason a session is lost.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

from savecloud.config.constants import log_dir

#
# Kept small deliberately. This is read by a person diagnosing
# something that happened recently, not mined for statistics, and a
# beta tester should be able to attach one to a report.
#

MAX_BYTES = 1_000_000

BACKUPS = 3

FILENAME = "savecloud.log"

#
# The environment variable is for a bug report: it turns on the detail
# that is normally too noisy to keep, without a rebuild or a flag on
# every command.
#

LEVEL_ENV = "SAVECLOUD_LOG_LEVEL"

_configured = False


def path() -> Path:
    """
    Where the log is written.
    """

    return log_dir() / FILENAME


def configure(force: bool = False) -> None:
    """
    Start writing to the log, once per process.

    Safe to call from anywhere and safe to call repeatedly. A failure
    to set it up is swallowed: an unwritable log directory is not a
    reason to refuse to synchronize a save.
    """

    global _configured

    if _configured and not force:
        return

    _configured = True

    try:
        directory = log_dir()

        directory.mkdir(parents=True, exist_ok=True)

        handler = logging.handlers.RotatingFileHandler(
            directory / FILENAME,
            maxBytes=MAX_BYTES,
            backupCount=BACKUPS,
            encoding="utf-8",
        )

        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-7s %(name)-28s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

        root = logging.getLogger("savecloud")

        #
        # Replace rather than add, so a second call - or a test that
        # forced reconfiguration - does not write every line twice.
        #

        for existing in list(root.handlers):
            root.removeHandler(existing)

            existing.close()

        root.addHandler(handler)

        root.setLevel(_level())

        #
        # The interface and the CLI both print their own messages, and
        # a log line escaping to the terminal alongside them would be
        # noise in the one place output is already handled.
        #

        root.propagate = False

    except Exception:
        #
        # Deliberately silent. Complaining about the log on every
        # command would be worse than not having one.
        #
        pass


def logger(name: str) -> logging.Logger:
    """
    Return a logger, configuring the journal on first use.
    """

    configure()

    return logging.getLogger(f"savecloud.{name}")


def recent(lines: int = 50) -> list[str]:
    """
    Return the last lines written, oldest first.

    Reads the current file only. A rotation means the older half is in
    `savecloud.log.1`, which is the rarer thing to want and always
    available by opening it.
    """

    try:
        with path().open("r", encoding="utf-8", errors="replace") as file:
            return [line.rstrip("\n") for line in file][-lines:]

    except OSError:
        return []


def _level() -> int:
    """
    How much to record.

    INFO covers what a person diagnosing a lost save needs: what
    synchronization decided and what failed. DEBUG adds per-file
    transfer detail, which is the difference between a log worth
    reading and a log worth grepping.
    """

    requested = os.environ.get(LEVEL_ENV, "").strip().upper()

    return getattr(logging, requested, logging.INFO) if requested else logging.INFO
