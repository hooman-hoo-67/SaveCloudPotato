"""
Tests for making a downloaded AppImage behave like an installed
program.

An AppImage is one file that has been downloaded, not installed: not
on PATH, no menu entry. Neither is required for it to work, which is
why this is offered rather than performed.
"""

from __future__ import annotations

import os
import sys

import pytest

from savecloud.services import integration


@pytest.fixture
def home(tmp_path, monkeypatch):
    """
    A home directory this test may write into.
    """

    monkeypatch.setenv("HOME", str(tmp_path))

    monkeypatch.setattr(
        integration,
        "BIN",
        tmp_path / ".local" / "bin",
        raising=False,
    )

    monkeypatch.setattr(
        integration, "COMMAND", tmp_path / ".local" / "bin" / "savecloud"
    )

    monkeypatch.setattr(
        integration,
        "APPLICATIONS",
        tmp_path / ".local" / "share" / "applications",
    )

    monkeypatch.setattr(
        integration,
        "DESKTOP_ENTRY",
        tmp_path / ".local" / "share" / "applications" / "savecloud.desktop",
    )

    icons = tmp_path / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"

    monkeypatch.setattr(integration, "ICONS", icons)

    monkeypatch.setattr(integration, "ICON", icons / "savecloud.png")

    return tmp_path


@pytest.fixture
def appimage(tmp_path, monkeypatch):
    """
    Pretend to be running from a downloaded AppImage.
    """

    bundle = tmp_path / "SaveCloud-x86_64.AppImage"

    bundle.write_text("#!/bin/sh\n")

    bundle.chmod(0o755)

    monkeypatch.setenv("APPIMAGE", str(bundle))

    return bundle


#
# Whether there is anything to do
#


def test_a_downloaded_build_is_offered_the_choice(appimage):

    assert integration.is_packaged() is True


def test_a_pip_installation_is_not(monkeypatch):
    """
    It is already on PATH; there is nothing to link.
    """

    monkeypatch.delenv("APPIMAGE", raising=False)

    assert integration.is_packaged() is False


#
# Installing
#


def test_the_command_becomes_reachable_by_name(home, appimage):

    result = integration.install()

    assert result.ok is True

    assert integration.COMMAND.is_symlink()

    assert integration.COMMAND.resolve() == appimage.resolve()


def test_a_symlink_rather_than_a_copy(home, appimage):
    """
    Replacing the AppImage should update the command, not leave a
    stale copy behind.
    """

    integration.install()

    appimage.write_text("#!/bin/sh\n# a newer build\n")

    assert integration.COMMAND.read_text().endswith("a newer build\n")


def test_installing_twice_is_harmless(home, appimage):

    integration.install()

    result = integration.install()

    assert result.ok is True

    assert integration.COMMAND.resolve() == appimage.resolve()


def test_it_replaces_a_link_to_an_older_build(home, appimage, tmp_path):

    old = tmp_path / "Old.AppImage"

    old.write_text("#!/bin/sh\n")

    old.chmod(0o755)

    integration.BIN.mkdir(parents=True)

    integration.COMMAND.symlink_to(old)

    integration.install()

    assert integration.COMMAND.resolve() == appimage.resolve()


def test_the_menu_entry_names_the_real_file(home, appimage):
    """
    A desktop entry is read by things that do not share this
    process's PATH, so a bare name would not resolve.
    """

    integration.install()

    entry = integration.DESKTOP_ENTRY.read_text()

    assert f"Exec={appimage}" in entry

    assert "Name=SaveCloud" in entry


def test_a_missing_path_entry_is_reported(home, appimage, monkeypatch):
    """
    Silently creating a command nobody can run would be worse than
    saying so.
    """

    monkeypatch.setenv("PATH", "/usr/bin")

    result = integration.install()

    assert result.ok is True

    assert any("PATH" in warning for warning in result.warnings)


def test_a_present_path_entry_is_not_reported(home, appimage, monkeypatch):

    monkeypatch.setenv("PATH", f"{integration.BIN}{os.pathsep}/usr/bin")

    result = integration.install()

    assert not any("PATH" in warning for warning in result.warnings)


def test_it_reports_what_it_created(home, appimage):

    result = integration.install()

    assert str(integration.COMMAND) in result.created

    assert str(integration.DESKTOP_ENTRY) in result.created


def test_it_fails_clearly_when_there_is_nothing_to_link(home, monkeypatch):

    monkeypatch.delenv("APPIMAGE", raising=False)

    monkeypatch.setattr(sys, "argv", ["pytest"])

    monkeypatch.setattr(sys, "executable", "/nowhere/python")

    monkeypatch.setattr(sys, "prefix", "/nowhere")

    monkeypatch.setenv("PATH", "")

    result = integration.install()

    assert result.ok is False

    assert "could not find" in result.message.lower()


#
# Removing
#


def test_removing_undoes_it(home, appimage):

    integration.install()

    result = integration.remove()

    assert result.ok is True

    assert not integration.COMMAND.exists()

    assert not integration.DESKTOP_ENTRY.exists()


def test_removing_leaves_the_appimage_alone(home, appimage):
    """
    This removes the ways of reaching SaveCloud, not SaveCloud.
    """

    integration.install()

    integration.remove()

    assert appimage.exists()


def test_removing_nothing_is_not_an_error(home):

    result = integration.remove()

    assert result.ok is True

    assert "Nothing" in result.message


#
# What the launch options become
#


def test_launch_options_prefer_the_installed_command(
    home,
    appimage,
    monkeypatch,
):
    """
    Steam keeps launch options until they are edited by hand, so the
    path written into them should outlive replacing the AppImage.
    """

    from savecloud.utils import executable

    monkeypatch.setattr(
        executable.Path, "home", classmethod(lambda cls: home)
    )

    integration.install()

    assert launch_target(executable) == str(integration.COMMAND)


def test_launch_options_use_the_bundle_before_installing(
    home,
    appimage,
    monkeypatch,
):

    from savecloud.utils import executable

    monkeypatch.setattr(
        executable.Path, "home", classmethod(lambda cls: home)
    )

    assert launch_target(executable) == str(appimage)


def launch_target(executable_module) -> str:
    """
    The program named at the front of the launch options.
    """

    options = executable_module.launch_options("zelda")

    return options.split(" wrap ")[0].strip("'\"")
