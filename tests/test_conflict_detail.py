"""
Tests for describing the two sides of a conflict.

Resolving a conflict means keeping one save and discarding the other.
Two checksums do not help with that: they are equally opaque, and
neither says which machine the other save came from or how recently
someone was playing on it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from savecloud.models.save_summary import SaveSummary, describe_age
from savecloud.services.registry import RegistryService
from savecloud.services.sync import SyncConflictError, SyncService
from savecloud.storage import LocalStorageBackend

from tests.conftest import GAME_ID, write_save
from tests.test_sync import advance_remote


#
# Rendering an age
#


def test_ages_are_rendered_in_words():

    now = datetime.now(UTC)

    assert describe_age(now - timedelta(seconds=5), now) == "just now"

    assert describe_age(now - timedelta(minutes=1), now) == "1 minute ago"

    assert describe_age(now - timedelta(minutes=42), now) == "42 minutes ago"

    assert describe_age(now - timedelta(hours=5), now) == "5 hours ago"

    assert describe_age(now - timedelta(days=1), now) == "1 day ago"

    assert describe_age(now - timedelta(days=200), now) == "6 months ago"


def test_a_missing_moment_renders_as_nothing():

    assert describe_age(None) == ""


def test_a_save_from_the_future_says_so():
    """
    Clocks disagree between devices. Saying so is more honest than
    rendering a negative interval.
    """

    now = datetime.now(UTC)

    assert "clocks" in describe_age(now + timedelta(hours=2), now)


def test_a_description_names_the_place_and_the_age():

    summary = SaveSummary(
        where="Steam Deck",
        modified="2026-07-29 14:00",
        age="2 hours ago",
        version=7,
        checksum="abc",
    )

    assert summary.description == "Steam Deck · saved 2 hours ago · version 7"


def test_a_description_omits_what_it_does_not_know():

    summary = SaveSummary(
        where="Another device",
        modified="unknown",
        age="",
        version=0,
        checksum="",
    )

    assert summary.description == "Another device"


#
# Describing the real thing
#


def test_the_local_side_is_named_and_dated(registered_game, working_save):


    write_save(working_save, "progress")

    summary = SyncService.describe_local(RegistryService.load_game(GAME_ID))

    assert summary.where == "This device"

    assert summary.age

    assert summary.checksum


def test_the_local_side_reads_the_working_save(registered_game, working_save):
    """
    What is being offered is the save as it is now, not as it was when
    something was last recorded about it.
    """

    write_save(working_save, "played offline")

    summary = SyncService.describe_local(RegistryService.load_game(GAME_ID))

    assert summary.age in {"just now", "1 minute ago"}


def test_the_remote_side_is_named_after_the_device_that_uploaded_it(
    registered_game,
    working_save,
):
    """
    The whole point: someone choosing needs to know whose save it is.
    """

    write_save(working_save, "progress")

    SyncService.sync(RegistryService.load_game(GAME_ID))

    from savecloud.services.library import SaveCloudLibrary

    state = LocalStorageBackend.state(GAME_ID)

    assert state.device_name == SaveCloudLibrary.device_name()

    summary = SyncService.describe_remote(state)

    assert summary.where == SaveCloudLibrary.device_name()

    assert summary.age


def test_an_unclaimed_remote_is_not_given_a_name(registered_game):
    """
    A remote written by an older version, or by a plain file copy, has
    nothing identifying it.
    """

    from savecloud.models.remote_state import RemoteState

    state = RemoteState.create(
        game_id=GAME_ID,
        checksum="abc",
        version=1,
        device_id="",
        device_name="",
    )

    assert SyncService.describe_remote(state).where == "Another device"


def test_no_remote_describes_as_nothing():

    assert SyncService.describe_remote(None) is None


#
# What the conflict carries
#


def test_a_conflict_carries_both_summaries(registered_game, working_save):

    SyncService.sync(RegistryService.load_game(GAME_ID))

    advance_remote(GAME_ID, "remote progress")

    write_save(working_save, "local progress")

    with pytest.raises(SyncConflictError) as raised:
        SyncService.sync(RegistryService.load_game(GAME_ID))

    error = raised.value

    assert error.local is not None

    assert error.remote is not None

    assert error.local.where == "This device"

    assert error.local.checksum != error.remote.checksum


#
# How it reaches the user
#


def test_the_cli_describes_both_saves(registered_game, working_save):

    from typer.testing import CliRunner

    from savecloud.cli import app

    SyncService.sync(RegistryService.load_game(GAME_ID))

    advance_remote(GAME_ID, "remote progress")

    write_save(working_save, "local progress")

    result = CliRunner().invoke(app, ["sync", GAME_ID])

    assert result.exit_code == 1

    assert "keep-local" in result.output

    assert "This device" in result.output

    assert "saved" in result.output


def test_the_json_form_carries_both_saves(registered_game, working_save):

    import json

    from typer.testing import CliRunner

    from savecloud.cli import app

    SyncService.sync(RegistryService.load_game(GAME_ID))

    advance_remote(GAME_ID, "remote progress")

    write_save(working_save, "local progress")

    result = CliRunner().invoke(app, ["--json", "sync", GAME_ID])

    payload = json.loads(result.stdout)

    assert payload["action"] == "conflict"

    assert payload["local"]["where"] == "This device"

    assert payload["remote"]["where"]

    assert payload["local"]["checksum"] != payload["remote"]["checksum"]


def test_the_facade_carries_both_saves(registered_game, working_save):

    from savecloud.gui.facade import GuiFacade

    GuiFacade.sync(GAME_ID)

    advance_remote(GAME_ID, "remote progress")

    write_save(working_save, "local progress")

    outcome = GuiFacade.sync(GAME_ID)

    assert outcome.conflict is True

    assert outcome.local.where == "This device"

    assert outcome.remote is not None


def test_the_dialog_buttons_name_the_devices(registered_game, working_save):
    """
    "Keep Steam Deck" says which save is being kept; "Keep the remote
    save" only says where it happens to live.
    """

    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)

    from savecloud.gui.window import _side

    assert _side(None, "the remote") == "the remote"

    assert (
        _side(
            SaveSummary(
                where="This device",
                modified="",
                age="",
                version=0,
                checksum="",
            ),
            "fallback",
        )
        == "this device"
    )

    assert (
        _side(
            SaveSummary(
                where="Steam Deck",
                modified="",
                age="",
                version=0,
                checksum="",
            ),
            "fallback",
        )
        == "Steam Deck"
    )
