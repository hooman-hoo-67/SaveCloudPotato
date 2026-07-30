"""
One writer per game.

Two SaveCloud processes can now reach the same game. The interface has
a Sync all button; Steam starts `wrap` independently; a terminal is
always available. Nothing stopped them interleaving.

The dangerous overlap is not two syncs racing to write a file - it is
a sync deciding what to do while a session is in progress. A download
replaces `current/` and publishes it to the working save directory,
which for a running game means overwriting the file it has open. And
both processes write `runtime.json`, where `last_sync_checksum` lives:
lose that and conflict detection loses the ancestor it compares
against, which is the mechanism, not a convenience.

So a game is held for as long as something is acting on it, and a
session holds it for as long as the game runs. Anything else asking
is told what is happening rather than left to interleave.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path

from savecloud.config.constants import cache_dir

try:
    import fcntl

except ImportError:
    #
    # Windows. Support there is unverified anyway, and refusing to run
    # would be a worse answer than running unprotected - which is what
    # every version until now did.
    #

    fcntl = None


#
# How long to wait for a lock before giving up. Long enough to cover
# another sync finishing, short enough that a command does not appear
# to hang.
#

TIMEOUT_SECONDS = 5.0

POLL_SECONDS = 0.1

#
# Marks a claim that will not be over in a moment. A session lasts as
# long as someone plays, so waiting for one is never the right answer:
# an unwinnable five-second wait ending in a timeout describes the
# situation far worse than refusing immediately does.
#

SESSION = "session"


class GameBusyError(RuntimeError):
    """
    Raised when another process is already acting on a game.
    """

    def __init__(self, game_id: str, holder: str) -> None:

        super().__init__(
            f'"{game_id}" is in use by another SaveCloud process'
            + (f" ({holder})" if holder else "")
            + "."
        )

        self.game_id = game_id
        self.holder = holder


class GameLock:
    """
    An exclusive claim on one game, shared across processes.
    """

    #
    # Depth per game, so a session that already holds the lock can
    # call something that takes it again. flock is per file
    # descriptor, so without this the inner acquire would succeed and
    # the inner release would drop the outer one's claim.
    #

    _depth: dict[str, int] = {}

    _handles: dict[str, int] = {}

    @staticmethod
    def directory() -> Path:
        """
        Where lock files live.

        Under `cache/`, which is documented as safe to delete: a lock
        file left behind by a crash means nothing once no process holds
        it, because the claim is the flock and not the file.
        """

        return cache_dir() / "locks"

    @staticmethod
    def path(game_id: str) -> Path:
        """
        The lock file for a game.
        """

        return GameLock.directory() / f"{game_id}.lock"

    @classmethod
    @contextmanager
    def hold(
        cls,
        game_id: str,
        reason: str = "",
        timeout: float = TIMEOUT_SECONDS,
        long_lived: bool = False,
    ):
        """
        Hold a game for the duration of the block.

        Parameters
        ----------
        game_id
            Game to claim.
        reason
            What is being done, recorded in the lock file so another
            process can say something better than "busy".
        timeout
            How long to wait before raising. Ignored when the current
            holder is long-lived.
        long_lived
            Whether this claim lasts as long as someone is playing
            rather than as long as an operation takes. Anything asking
            for a game held this way is refused at once instead of
            waiting for something that will not finish soon.

        Raises
        ------
        GameBusyError
            If another process holds the game.
        """

        if fcntl is None:
            yield

            return

        if cls._depth.get(game_id):
            cls._depth[game_id] += 1

            try:
                yield

            finally:
                cls._depth[game_id] -= 1

            return

        path = cls.path(game_id)

        path.parent.mkdir(parents=True, exist_ok=True)

        handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)

        try:
            cls._acquire(handle, game_id, path, timeout)

        except BaseException:
            os.close(handle)

            raise

        cls._handles[game_id] = handle

        cls._depth[game_id] = 1

        try:
            os.truncate(handle, 0)

            os.write(
                handle,
                f"{os.getpid()} {SESSION if long_lived else 'operation'} "
                f"{reason}".encode(),
            )

            os.fsync(handle)

            yield

        finally:
            cls._depth.pop(game_id, None)

            cls._handles.pop(game_id, None)

            try:
                os.truncate(handle, 0)

                fcntl.flock(handle, fcntl.LOCK_UN)

            except OSError:
                pass

            os.close(handle)

    @classmethod
    def _acquire(
        cls,
        handle: int,
        game_id: str,
        path: Path,
        timeout: float,
    ) -> None:
        """
        Take the flock, or raise saying who has it.
        """

        deadline = time.monotonic() + timeout

        while True:

            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

                return

            except OSError:

                kind, holder = cls._recorded(path)

                #
                # A session will not be finished in a moment, so
                # waiting for it only delays the same refusal.
                #

                if kind == SESSION:
                    raise GameBusyError(game_id, holder)

                if time.monotonic() >= deadline:
                    raise GameBusyError(game_id, holder)

                time.sleep(POLL_SECONDS)

    @staticmethod
    def _recorded(path: Path) -> tuple[str, str]:
        """
        What the holding process said: its kind, and what it is doing.
        """

        try:
            recorded = path.read_text(encoding="utf-8").strip()

        except OSError:
            return "", ""

        parts = recorded.split(" ", 2)

        kind = parts[1] if len(parts) > 1 else ""

        reason = parts[2] if len(parts) > 2 else ""

        return kind, reason.strip()
