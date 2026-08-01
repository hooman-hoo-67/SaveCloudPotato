"""
What a game ID is allowed to be.

An ID names a directory in the library, the registry, every storage
backend, and a lock file. So these are not cosmetic rules: an ID with a
separator in it does not name a game badly, it names a different place.
"""

from __future__ import annotations

import pytest

from savecloud.config.constants import registry_dir
from savecloud.models.game import (
    Game,
    GameManifest,
    GameRuntime,
    LaunchType,
    Platform,
)
from savecloud.services.registry import RegistryService
from savecloud.utils.identifiers import InvalidGameIdError, validate_game_id


def build(game_id: str) -> Game:

    return Game(
        manifest=GameManifest(
            game_id=game_id,
            display_name="Test",
            launch_type=LaunchType.MANUAL,
            platform=Platform.NATIVE,
            adapter="manual",
        ),
        runtime=GameRuntime(),
    )


@pytest.mark.parametrize(
    "game_id",
    [
        "pokemon-scarlet",
        "zelda_totk",
        "Game 2",
        "sonic.adventure.2",
        "0100F2C0115B6000",
    ],
)
def test_ordinary_ids_are_accepted(game_id):

    assert validate_game_id(game_id) == game_id


@pytest.mark.parametrize(
    "game_id",
    [
        "pokemon black/white",
        "windows\\style",
        "../escaped",
        "..",
        ".",
        "",
        "   ",
        " leading",
        "trailing ",
        "ends.",
        "con",
        "LPT1",
        'quote"mark',
        "star*",
        "null\x00byte",
        "x" * 101,
    ],
)
def test_ids_that_would_name_a_folder_badly_are_refused(game_id):

    with pytest.raises(InvalidGameIdError):
        validate_game_id(game_id)


def test_the_message_names_the_character():
    """
    The usual way here is a title that genuinely contains a slash.
    """

    with pytest.raises(InvalidGameIdError) as raised:
        validate_game_id("pokemon black/white")

    assert "/" in str(raised.value)


#
# Registration
#


def test_registering_a_separator_id_is_refused():
    """
    It used to succeed, then vanish.

    A manifest one directory deeper than anything looks: `list` walks a
    single level, so the game never appeared again - and could not be
    removed either, since `unregister` takes an ID it could no longer
    show you.
    """

    with pytest.raises(InvalidGameIdError):
        RegistryService.create_registry(build("pokemon black/white"))

    assert RegistryService.list_games() == []


def test_a_refused_registration_writes_nothing():

    with pytest.raises(InvalidGameIdError):
        RegistryService.create_registry(build("../escaped"))

    assert list(registry_dir().iterdir()) == []


def test_an_escaping_id_cannot_reach_outside_the_registry():
    """
    `../name` used to create a directory beside the library, not in it.
    """

    with pytest.raises(InvalidGameIdError):
        RegistryService.create_registry(build("../escaped"))

    assert not (registry_dir().parent / "escaped").exists()


def test_a_valid_id_still_registers():

    RegistryService.create_registry(build("ordinary-game"))

    registered = [g.manifest.game_id for g in RegistryService.list_games()]

    assert registered == ["ordinary-game"]
