"""
Tests for atomic writes and per-game locking.

Two SaveCloud processes can now reach the same game: the interface has
a Sync all button, Steam starts `wrap` independently, and a terminal is
always available. Neither of these mechanisms is visible when it works,
which is why they are tested rather than trusted.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from savecloud.services.locking import GameBusyError, GameLock
from savecloud.services.registry import RegistryService
from savecloud.utils.atomic import write_json, write_text

from tests.conftest import GAME_ID


#
# Atomic writes
#


def test_a_document_is_replaced_whole(tmp_path):

    target = tmp_path / "runtime.json"

    write_json(target, {"version": 1})

    write_json(target, {"version": 2})

    assert json.loads(target.read_text()) == {"version": 2}


def test_no_temporary_file_is_left_behind(tmp_path):

    #
    # Its own directory: the installation fixture already occupies
    # tmp_path.
    #

    directory = tmp_path / "documents"

    directory.mkdir()

    write_json(directory / "state.json", {"a": 1})

    assert [path.name for path in directory.iterdir()] == ["state.json"]


def test_a_failed_write_leaves_the_previous_contents(tmp_path, monkeypatch):
    """
    The point of the rename: a write that dies takes the temporary file
    with it, not the document.
    """

    directory = tmp_path / "documents"

    directory.mkdir()

    target = directory / "runtime.json"

    write_json(target, {"good": True})

    def explode(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", explode)

    with pytest.raises(OSError):
        write_json(target, {"bad": True})

    assert json.loads(target.read_text()) == {"good": True}

    #
    # And nothing is left over from the attempt.
    #

    assert [path.name for path in directory.iterdir()] == ["runtime.json"]


def test_a_private_document_is_never_briefly_readable(tmp_path):
    """
    A token must not become world-readable on the way through.
    """

    target = tmp_path / "dropbox.json"

    write_json(target, {"refresh_token": "secret"}, mode=0o600)

    assert target.stat().st_mode & 0o777 == 0o600


def test_the_temporary_file_shares_the_filesystem(tmp_path, monkeypatch):
    """
    A rename across filesystems is not atomic, and on Linux is not a
    rename at all.
    """

    seen = {}

    import tempfile as tempfile_module

    real = tempfile_module.mkstemp

    def record(*args, **kwargs):
        seen["dir"] = kwargs.get("dir")

        return real(*args, **kwargs)

    monkeypatch.setattr(tempfile_module, "mkstemp", record)

    write_text(tmp_path / "file.txt", "x")

    assert seen["dir"] == tmp_path


def test_runtime_documents_are_written_atomically(registered_game, monkeypatch):
    """
    runtime.json holds last_sync_checksum, which is the ancestor
    conflict detection compares against.
    """

    calls = []

    import savecloud.services.registry as registry_module

    real = registry_module.write_json

    def record(path, data, **kwargs):
        calls.append(Path(path).name)

        return real(path, data, **kwargs)

    monkeypatch.setattr(registry_module, "write_json", record)

    game = RegistryService.load_game(GAME_ID)

    game.runtime.mark_pending()

    RegistryService.update_runtime(game)

    assert "runtime.json" in calls


#
# Locking
#


def test_a_game_can_be_held(registered_game):

    with GameLock.hold(GAME_ID, "testing"):
        assert GameLock.path(GAME_ID).exists()


def test_holding_is_reentrant_within_a_process(registered_game):
    """
    flock is per file descriptor, so without this the inner release
    would drop the outer claim.
    """

    with GameLock.hold(GAME_ID, "outer"):

        with GameLock.hold(GAME_ID, "inner"):
            pass

        #
        # Still held: an operation nested inside another has not
        # released it on the way out.
        #

        assert GameLock._depth.get(GAME_ID) == 1


def test_different_games_do_not_block_each_other(registered_game):

    with GameLock.hold(GAME_ID, "one"):

        with GameLock.hold("another-game", "two"):
            pass


def test_the_lock_is_released_when_the_block_raises(registered_game):

    with pytest.raises(RuntimeError):

        with GameLock.hold(GAME_ID, "failing"):
            raise RuntimeError("something went wrong")

    #
    # Available again immediately.
    #

    with GameLock.hold(GAME_ID, "after"):
        pass


def test_the_holder_records_what_it_is_doing(registered_game):

    with GameLock.hold(GAME_ID, "synchronizing"):

        recorded = GameLock.path(GAME_ID).read_text()

        assert "synchronizing" in recorded

        assert str(os.getpid()) in recorded


#
# Across processes, which is the only place this matters
#


HOLDER = """
import sys, time
sys.path.insert(0, {root!r})
from savecloud.services.locking import GameLock
with GameLock.hold({game!r}, {reason!r}, long_lived={long_lived!r}):
    print("held", flush=True)
    time.sleep(30)
"""


@pytest.fixture
def holder(tmp_path, request):
    """
    Start another process that holds a game, and stop it afterwards.
    """

    started = []

    def start(game_id: str, reason: str, long_lived: bool):

        script = HOLDER.format(
            root=str(Path(__file__).resolve().parent.parent),
            game=game_id,
            reason=reason,
            long_lived=long_lived,
        )

        process = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            env={**os.environ},
            text=True,
        )

        started.append(process)

        #
        # Wait until it says it has the lock, so the test is not racing
        # the interpreter starting up.
        #

        assert process.stdout.readline().strip() == "held"

        return process

    yield start

    for process in started:
        process.terminate()

        process.wait(timeout=10)


def test_another_process_is_refused(registered_game, holder):

    holder(GAME_ID, "synchronizing", False)

    with pytest.raises(GameBusyError):
        with GameLock.hold(GAME_ID, "mine", timeout=0.5):
            pass


def test_the_refusal_says_what_the_holder_is_doing(registered_game, holder):

    holder(GAME_ID, "synchronizing", False)

    with pytest.raises(GameBusyError) as raised:
        with GameLock.hold(GAME_ID, "mine", timeout=0.5):
            pass

    assert "synchronizing" in str(raised.value)


def test_a_session_is_refused_at_once_rather_than_waited_for(
    registered_game,
    holder,
):
    """
    A session lasts as long as someone plays. An unwinnable wait
    ending in a timeout describes that far worse than refusing does.
    """

    holder(GAME_ID, "playing", True)

    started = time.monotonic()

    with pytest.raises(GameBusyError):
        with GameLock.hold(GAME_ID, "mine", timeout=30.0):
            pass

    #
    # Refused without serving the thirty-second timeout.
    #

    assert time.monotonic() - started < 2.0


def test_an_operation_is_waited_for_briefly(registered_game, holder):
    """
    Another sync finishing is worth waiting a moment for.
    """

    holder(GAME_ID, "synchronizing", False)

    started = time.monotonic()

    with pytest.raises(GameBusyError):
        with GameLock.hold(GAME_ID, "mine", timeout=1.0):
            pass

    assert time.monotonic() - started >= 1.0


def test_a_different_game_is_unaffected_across_processes(
    registered_game,
    holder,
):

    holder(GAME_ID, "playing", True)

    with GameLock.hold("some-other-game", "mine", timeout=0.5):
        pass
