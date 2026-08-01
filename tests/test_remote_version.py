"""
Which version an upload says it is.

`RemoteState.version` is what the other device reads when it describes
a save someone has to choose between. It was being taken from
`GameRuntime.current_version`, which is written once at registration
and never advanced - so every upload was stamped version 0.

Zero renders as nothing at all, because `SaveSummary.description` omits
a falsy version. The visible symptom was a conflict that described the
local save fully and the remote one without a version, which is
precisely the comparison the conflict dialog exists to offer.
"""

from __future__ import annotations

from savecloud.services.library import SaveCloudLibrary
from savecloud.services.registry import RegistryService
from savecloud.services.sync import SyncService
from savecloud.storage.local import LocalStorageBackend
from tests.conftest import GAME_ID, write_save


def remote_version() -> int:

    return LocalStorageBackend.state(GAME_ID).version


def test_the_first_upload_is_version_one(registered_game):

    SyncService.sync(registered_game)

    assert SaveCloudLibrary.load_library_metadata(GAME_ID).latest_version == 1

    assert remote_version() == 1


def test_the_version_advances_with_the_library(registered_game, working_save):
    """
    Three saves, three versions - not three zeroes.
    """

    seen = []

    for number in range(1, 4):

        write_save(working_save, f"progress {number}")

        SyncService.sync(RegistryService.load_game(GAME_ID))

        seen.append(remote_version())

    assert seen == [1, 2, 3]


def test_the_uploaded_version_matches_the_library(
    registered_game,
    working_save,
):
    """
    The two counts must not drift, whichever the reader trusts.
    """

    write_save(working_save, "progress")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    assert (
        remote_version()
        == SaveCloudLibrary.load_library_metadata(GAME_ID).latest_version
    )


def test_a_described_remote_save_names_its_version(
    registered_game,
    working_save,
):
    """
    What the conflict dialog actually renders.
    """

    write_save(working_save, "progress")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    state = LocalStorageBackend.state(GAME_ID)

    summary = SyncService.describe_remote(state)

    assert summary is not None

    assert "version" in summary.description
