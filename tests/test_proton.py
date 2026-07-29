"""
Tests for registering a Proton game.

Proton gives each game an emulated Windows drive under
`steamapps/compatdata/<app-id>/pfx`. The prefix can be found; the save
inside it cannot, because Windows games follow no convention. So this
finds the prefix and asks about the rest.
"""

from __future__ import annotations

import pytest

from savecloud.gui.facade import GuiFacade

pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture
def steam(tmp_path, monkeypatch):
    """
    A Steam installation with two games and populated prefixes.
    """

    root = tmp_path / "Steam"

    apps = root / "steamapps"

    apps.mkdir(parents=True)

    (apps / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n\t"0"\n\t{{\n\t\t"path"\t\t"{root}"\n'
        '\t\t"apps"\n\t\t{\n\t\t\t"367520"\t\t"1"\n'
        '\t\t\t"2050650"\t\t"2"\n\t\t}\n\t}\n}\n'
    )

    for app_id, name in (("367520", "Hollow Knight"), ("2050650", "Resident Evil 4")):

        (apps / f"appmanifest_{app_id}.acf").write_text(
            f'"AppState"\n{{\n\t"appid"\t\t"{app_id}"\n'
            f'\t"name"\t\t"{name}"\n\t"installdir"\t\t"{name}"\n}}\n'
        )

        user = (
            apps
            / "compatdata"
            / app_id
            / "pfx"
            / "drive_c"
            / "users"
            / "steamuser"
        )

        (user / "AppData" / "Roaming" / name).mkdir(parents=True)

        (user / "Documents" / "My Games" / name).mkdir(parents=True)

    monkeypatch.setenv("SAVECLOUD_STEAM_ROOT", str(root))

    return root


@pytest.fixture
def qt_app():

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    yield app

    from savecloud.gui import worker

    worker.wait()

    app.processEvents()


#
# What the facade offers
#


def test_installed_games_are_listed(steam):

    games = GuiFacade.steam_games()

    assert [game.app_id for game in games] == ["367520", "2050650"]

    assert games[0].name == "Hollow Knight"


def test_games_are_listed_alphabetically(steam):

    names = [game.name for game in GuiFacade.steam_games()]

    assert names == sorted(names, key=str.lower)


def test_the_label_carries_the_app_id(steam):
    """
    Two games can share a name; App IDs do not.
    """

    assert "(367520)" in GuiFacade.steam_games()[0].label


def test_the_prefix_is_found(steam):

    root = GuiFacade.prefix_root("2050650")

    assert root.endswith("drive_c/users/steamuser")


def test_a_game_with_no_prefix_reports_nothing(steam):

    assert GuiFacade.prefix_root("999999") == ""


def test_plausible_save_folders_are_offered(steam):

    candidates = GuiFacade.save_candidates("2050650")

    assert len(candidates) == 2

    assert any("AppData/Roaming/Resident Evil 4" in path for path in candidates)

    assert any(
        "Documents/My Games/Resident Evil 4" in path for path in candidates
    )


def test_a_container_is_not_offered_as_a_save(steam):
    """
    Documents contains My Games, so offering Documents itself would
    synchronize both and everything else in there.
    """

    candidates = GuiFacade.save_candidates("2050650")

    assert not any(path.endswith("/Documents") for path in candidates)


#
# Building the identifier
#


def test_the_identifier_is_relative_to_the_prefix(steam):
    """
    Steam moves prefixes between libraries when a game changes drive,
    so an absolute path would not survive it.
    """

    folder = GuiFacade.save_candidates("2050650")[0]

    outcome = GuiFacade.steam_identifier("2050650", folder)

    assert outcome.ok is True

    assert outcome.value == "2050650:AppData/Roaming/Resident Evil 4"


def test_the_identifier_round_trips_through_the_adapter(steam):

    folder = GuiFacade.save_candidates("2050650")[0]

    identifier = GuiFacade.steam_identifier("2050650", folder).value

    located = GuiFacade.locate_save("steam-proton", identifier)

    assert located.ok is True

    assert located.value == folder


def test_the_prefix_root_itself_is_allowed(steam):
    """
    A game that writes straight into the user directory.
    """

    outcome = GuiFacade.steam_identifier(
        "2050650",
        GuiFacade.prefix_root("2050650"),
    )

    assert outcome.ok is True

    assert outcome.value == "2050650"


def test_a_folder_outside_the_prefix_is_refused(steam, tmp_path):
    """
    Synchronizing something outside the prefix would be a mistake this
    could have caught.
    """

    outcome = GuiFacade.steam_identifier("2050650", str(tmp_path))

    assert outcome.ok is False

    assert "outside the game's prefix" in outcome.message


def test_a_game_never_launched_says_so(steam):

    outcome = GuiFacade.steam_identifier("999999", "/tmp")

    assert outcome.ok is False

    assert "Launch it once" in outcome.message


def test_choosing_nothing_is_refused(steam):

    assert GuiFacade.steam_identifier("", "/tmp").ok is False

    assert GuiFacade.steam_identifier("2050650", "").ok is False


#
# The form
#


def test_the_form_offers_the_installed_games(qt_app, steam):

    from savecloud.gui.dialogs import RegisterDialog

    dialog = RegisterDialog()

    dialog.adapter.setCurrentText("steam-proton")

    labels = [
        dialog.steam_game.itemText(index)
        for index in range(dialog.steam_game.count())
    ]

    assert any("Resident Evil 4" in label for label in labels)


def test_choosing_a_game_fills_in_its_save_folders(qt_app, steam):

    from savecloud.gui.dialogs import RegisterDialog

    dialog = RegisterDialog()

    dialog.adapter.setCurrentText("steam-proton")

    dialog.steam_game.setCurrentIndex(1)

    assert dialog.save_folder.count() == 2

    assert "Resident Evil 4" in dialog.save_folder.currentText()


def test_registering_a_proton_game_records_the_relative_path(
    qt_app,
    steam,
):

    from savecloud.gui.dialogs import ACCEPTED, RegisterDialog

    dialog = RegisterDialog()

    dialog.adapter.setCurrentText("steam-proton")

    dialog.platform.setCurrentText("proton")

    dialog.steam_game.setCurrentIndex(1)

    dialog.display_name.setText("Resident Evil 4")

    dialog.submit()

    assert dialog.result() == ACCEPTED

    detail = GuiFacade.detail("resident-evil-4")

    assert detail.adapter == "steam-proton"

    assert "AppData/Roaming/Resident Evil 4" in detail.working_save_path


def test_a_prefix_with_no_saves_says_what_to_do(qt_app, steam, tmp_path):
    """
    A game that has never written a save has nothing to offer.
    """

    from savecloud.gui.dialogs import RegisterDialog

    dialog = RegisterDialog()

    dialog.adapter.setCurrentText("steam-proton")

    #
    # Hollow Knight's prefix has the standard folders but no game
    # directory inside them, so there is nothing to guess at.
    #

    import shutil

    user = tmp_path / "Steam" / "steamapps" / "compatdata" / "367520" / "pfx"

    shutil.rmtree(user / "drive_c" / "users" / "steamuser" / "AppData")

    shutil.rmtree(user / "drive_c" / "users" / "steamuser" / "Documents")

    dialog._steam_game_changed()

    assert "Play the game once" in dialog.message.text()
