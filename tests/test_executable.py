"""
Tests for locating SaveCloud's own executable.

Steam launch options are handed to Steam, not to a shell that has
activated anything. A virtual environment's `bin` is not on the PATH
Steam runs with, so a bare `savecloud` resolves to nothing there and
the game fails to start with no explanation.
"""

from __future__ import annotations

import sys
from pathlib import Path

from savecloud.utils import executable
from savecloud.utils.executable import launch_options, savecloud_executable


def make_executable(path: Path) -> Path:
    """
    Create a file this system would run.
    """

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text("#!/bin/sh\n")

    path.chmod(0o755)

    return path


#
# Finding it
#


def test_it_is_found_beside_the_interpreter(tmp_path, monkeypatch):
    """
    The virtual environment case: both live in the same `bin`.
    """

    command = make_executable(tmp_path / "bin" / "savecloud")

    monkeypatch.setattr(sys, "executable", str(tmp_path / "bin" / "python"))

    monkeypatch.setattr(sys, "prefix", str(tmp_path))

    monkeypatch.setattr(sys, "argv", ["pytest"])

    assert savecloud_executable() == command


def test_a_symlinked_interpreter_does_not_lead_outside(tmp_path, monkeypatch):
    """
    A virtual environment's `python` is usually a symlink to the
    system interpreter. Following it lands where SaveCloud is not
    installed, which is exactly the wrong answer.
    """

    system = make_executable(tmp_path / "usr" / "bin" / "python3")

    venv_bin = tmp_path / "venv" / "bin"

    venv_bin.mkdir(parents=True)

    (venv_bin / "python").symlink_to(system)

    command = make_executable(venv_bin / "savecloud")

    monkeypatch.setattr(sys, "executable", str(venv_bin / "python"))

    monkeypatch.setattr(sys, "prefix", str(tmp_path / "venv"))

    monkeypatch.setattr(sys, "argv", ["pytest"])

    assert savecloud_executable() == command


def test_the_prefix_is_used_when_the_interpreter_is_elsewhere(
    tmp_path,
    monkeypatch,
):

    command = make_executable(tmp_path / "bin" / "savecloud")

    monkeypatch.setattr(sys, "executable", "/somewhere/else/python")

    monkeypatch.setattr(sys, "prefix", str(tmp_path))

    monkeypatch.setattr(sys, "argv", ["pytest"])

    assert savecloud_executable() == command


def test_how_this_process_started_wins(tmp_path, monkeypatch):
    """
    With several installations, the one actually running is the one
    whose options should be written.
    """

    running = make_executable(tmp_path / "running" / "savecloud")

    make_executable(tmp_path / "other" / "savecloud")

    monkeypatch.setattr(sys, "argv", [str(running)])

    monkeypatch.setattr(sys, "executable", str(tmp_path / "other" / "python"))

    monkeypatch.setattr(sys, "prefix", str(tmp_path / "other"))

    assert savecloud_executable() == running


def test_the_interface_script_resolves_to_the_command(tmp_path, monkeypatch):
    """
    `savecloud-gui` is a different script beside the same interpreter.
    """

    make_executable(tmp_path / "bin" / "savecloud-gui")

    command = make_executable(tmp_path / "bin" / "savecloud")

    monkeypatch.setattr(sys, "argv", [str(tmp_path / "bin" / "savecloud-gui")])

    assert savecloud_executable() == command


def test_path_is_the_last_resort(tmp_path, monkeypatch):
    """
    A pipx or system installation, where there is no environment to
    reason about.
    """

    command = make_executable(tmp_path / "elsewhere" / "savecloud")

    monkeypatch.setattr(sys, "argv", ["pytest"])

    monkeypatch.setattr(sys, "executable", "/nowhere/python")

    monkeypatch.setattr(sys, "prefix", "/nowhere")

    monkeypatch.setenv("PATH", str(tmp_path / "elsewhere"))

    assert savecloud_executable() == command


def test_nothing_is_found_when_run_from_source(tmp_path, monkeypatch):

    monkeypatch.setattr(sys, "argv", ["pytest"])

    monkeypatch.setattr(sys, "executable", "/nowhere/python")

    monkeypatch.setattr(sys, "prefix", "/nowhere")

    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    assert savecloud_executable() is None


def test_a_directory_is_not_mistaken_for_the_command(tmp_path, monkeypatch):

    (tmp_path / "bin" / "savecloud").mkdir(parents=True)

    monkeypatch.setattr(sys, "argv", ["pytest"])

    monkeypatch.setattr(sys, "executable", str(tmp_path / "bin" / "python"))

    monkeypatch.setattr(sys, "prefix", str(tmp_path))

    monkeypatch.setenv("PATH", "")

    assert savecloud_executable() is None


def test_a_file_that_cannot_be_executed_is_ignored(tmp_path, monkeypatch):

    command = tmp_path / "bin" / "savecloud"

    command.parent.mkdir(parents=True)

    command.write_text("")

    command.chmod(0o644)

    monkeypatch.setattr(sys, "argv", ["pytest"])

    monkeypatch.setattr(sys, "executable", str(tmp_path / "bin" / "python"))

    monkeypatch.setattr(sys, "prefix", str(tmp_path))

    monkeypatch.setenv("PATH", "")

    assert savecloud_executable() is None


#
# The line it produces
#


def test_the_absolute_path_is_used(tmp_path, monkeypatch):

    command = make_executable(tmp_path / "bin" / "savecloud")

    monkeypatch.setattr(sys, "argv", ["pytest"])

    monkeypatch.setattr(sys, "executable", str(tmp_path / "bin" / "python"))

    monkeypatch.setattr(sys, "prefix", str(tmp_path))

    assert launch_options("zelda") == f"{command} wrap zelda -- %command%"


def test_a_path_with_spaces_is_quoted(tmp_path, monkeypatch):
    """
    Steam splits the line, so an unquoted path would arrive as two
    arguments and nothing would run.
    """

    command = make_executable(tmp_path / "my games" / "bin" / "savecloud")

    monkeypatch.setattr(sys, "argv", [str(command)])

    options = launch_options("zelda")

    assert options.startswith("'")

    assert str(command) in options

    assert options.endswith("wrap zelda -- %command%")


def test_a_bare_name_is_the_fallback(monkeypatch):
    """
    Running from source, where there is no console script to point at.
    """

    monkeypatch.setattr(executable, "savecloud_executable", lambda: None)

    assert launch_options("zelda") == "savecloud wrap zelda -- %command%"


def test_the_game_id_is_always_present(tmp_path, monkeypatch):

    monkeypatch.setattr(sys, "argv", ["pytest"])

    monkeypatch.setattr(sys, "executable", "/nowhere/python")

    monkeypatch.setattr(sys, "prefix", "/nowhere")

    monkeypatch.setenv("PATH", "")

    assert "wrap pokemon-scarlet -- %command%" in (
        launch_options("pokemon-scarlet")
    )
