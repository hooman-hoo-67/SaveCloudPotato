"""
Tests for when version history is transferred.

At the end of a session someone is waiting to get back to their
desktop. History is not what another device needs in order to continue
playing - the current save is - so history follows at the next launch,
while the game is running and nobody is watching.
"""

from __future__ import annotations


from savecloud.services.autosync import AutoSyncService
from savecloud.services.registry import RegistryService
from savecloud.services.sync import SyncService
from savecloud.storage import LocalStorageBackend

from tests.conftest import GAME_ID, register_game, write_save


def playing_command(working_save, contents: str) -> str:
    """
    A launch command that writes save data, as a real game does.

    Needed here because a session that changes nothing creates no
    version, and this is a test about where versions go.
    """

    return f"sh -c \"printf '{contents}' > {working_save / 'save.dat'}\""


def stored_versions(game_id: str = GAME_ID) -> set[str]:
    """
    Version directories the backend holds.
    """

    remote = LocalStorageBackend.versions_directory(game_id)

    if not remote.exists():
        return set()

    return {path.name for path in remote.iterdir() if path.is_dir()}


def local_versions(game_id: str = GAME_ID) -> set[str]:
    """
    Version directories the library holds.
    """

    from savecloud.services.library import SaveCloudLibrary

    directory = SaveCloudLibrary.versions_directory(game_id)

    if not directory.exists():
        return set()

    return {path.name for path in directory.iterdir() if path.is_dir()}


#
# What each moment transfers
#


def test_an_explicit_upload_still_sends_history(registered_game, working_save):
    """
    Only a session defers. Asking for an upload sends everything.
    """

    write_save(working_save, "progress")

    SyncService.upload(RegistryService.load_game(GAME_ID))

    assert stored_versions() == local_versions()

    assert stored_versions()


def test_an_upload_can_leave_history_behind(registered_game, working_save):

    write_save(working_save, "progress")

    SyncService.upload(RegistryService.load_game(GAME_ID), history=False)

    assert local_versions()

    assert stored_versions() == set()


def test_the_current_save_still_arrives_without_history(
    registered_game,
    working_save,
):
    """
    The important half. Another device downloads this, not the history.
    """

    from tests.conftest import read_save

    write_save(working_save, "progress")

    SyncService.upload(RegistryService.load_game(GAME_ID), history=False)

    assert read_save(LocalStorageBackend.current_directory(GAME_ID)) == "progress"


def test_history_can_be_sent_on_its_own(registered_game, working_save):

    write_save(working_save, "progress")

    SyncService.upload(RegistryService.load_game(GAME_ID), history=False)

    assert stored_versions() == set()

    SyncService.push_history(RegistryService.load_game(GAME_ID))

    assert stored_versions() == local_versions()


#
# The session
#


def test_a_session_does_not_wait_for_history(tmp_path):

    working = tmp_path / "working"

    write_save(working, "before")

    register_game(working, launch_command="true")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    before = stored_versions()

    write_save(working, "after playing")

    #
    # No history transfer at exit: whatever the session created is
    # still only local.
    #

    AutoSyncService.after_exit(
        RegistryService.load_game(GAME_ID),
        0,
        AutoSyncService.play.__globals__["PlayResult"](exit_code=0),
    )

    assert local_versions() - stored_versions()

    assert stored_versions() == before


def test_the_next_launch_sends_what_the_last_session_created(tmp_path):
    """
    History catches up while the game runs.
    """

    working = tmp_path / "working"

    write_save(working, "before")

    game = register_game(
        working,
        launch_command=playing_command(working, "played once"),
    )

    AutoSyncService.play(game)

    pending = local_versions() - stored_versions()

    assert pending, "the session should have left history behind"

    RegistryService.delete_registry(GAME_ID)

    register_game(
        working,
        launch_command=playing_command(working, "played twice"),
    )

    AutoSyncService.play(RegistryService.load_game(GAME_ID))

    #
    # Everything the first session created has now arrived.
    #

    assert not pending - stored_versions()


def test_a_failed_history_transfer_does_not_disturb_the_session(
    tmp_path,
    monkeypatch,
):
    """
    History arriving late is not a reason to interfere with playing.
    """

    working = tmp_path / "working"

    write_save(working, "before")

    game = register_game(
        working,
        launch_command=playing_command(working, "played"),
    )

    def explode(game_id):
        raise RuntimeError("storage went away")

    monkeypatch.setattr(
        LocalStorageBackend,
        "push_history",
        classmethod(lambda cls, game_id: explode(game_id)),
    )

    result = AutoSyncService.play(game)

    assert result.exit_code == 0

    assert result.uploaded is True


def test_the_history_transfer_finishes_before_the_session_is_captured(
    tmp_path,
    monkeypatch,
):
    """
    Two transfers writing the same remote paths would be a race.
    """

    working = tmp_path / "working"

    write_save(working, "before")

    game = register_game(
        working,
        launch_command=playing_command(working, "played"),
    )

    order = []

    real_history = LocalStorageBackend.push_history

    def slow_history(cls, game_id):
        import time

        time.sleep(0.3)

        order.append("history")

        return real_history.__func__(cls, game_id)

    monkeypatch.setattr(
        LocalStorageBackend, "push_history", classmethod(slow_history)
    )

    real_upload = LocalStorageBackend.upload

    def note_upload(cls, game, history=True):
        order.append("capture-upload")

        return real_upload.__func__(cls, game, history=history)

    monkeypatch.setattr(LocalStorageBackend, "upload", classmethod(note_upload))

    AutoSyncService.play(game)

    #
    # The pre-launch sync uploads too, before the game starts and so
    # before the history thread exists. The one that must come after
    # history is the last: the session being published.
    #

    last_upload = max(
        index for index, event in enumerate(order)
        if event == "capture-upload"
    )

    assert order.index("history") < last_upload


def test_a_game_with_sync_off_starts_no_transfer(tmp_path):

    working = tmp_path / "working"

    write_save(working, "before")

    game = register_game(working, launch_command="true", sync_enabled=False)

    assert AutoSyncService._push_history_in_background(game) is None
