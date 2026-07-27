"""
Interactive prompt helpers.

Commands share these helpers so that every interactive flow presents
the same interface. Commands must never import one another; anything
reusable belongs here.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import typer


def prompt_required(text: str) -> str:
    """
    Prompt until a non-empty value is entered.
    """

    while True:
        value = typer.prompt(text).strip()

        if value:
            return value

        typer.secho(
            "Value cannot be empty.",
            fg=typer.colors.RED,
        )


def prompt_directory(
    text: str,
    must_exist: bool = True,
) -> Path:
    """
    Prompt for a directory path.
    """

    while True:
        path = Path(
            prompt_required(text),
        ).expanduser()

        if not must_exist:
            return path

        if path.is_dir():
            return path

        typer.secho(
            f"Not a directory: {path}",
            fg=typer.colors.RED,
        )


def choose_option(
    options: list[str],
    title: str,
) -> str:
    """
    Prompt the user to choose from a list of options.
    """

    if not options:
        raise ValueError("No options available.")

    if len(options) == 1:
        return options[0]

    typer.echo()
    typer.echo(title)

    for index, option in enumerate(
        options,
        start=1,
    ):
        typer.echo(f"{index}. {option}")

    while True:
        choice = typer.prompt(
            "Choice",
            type=int,
        )

        if 1 <= choice <= len(options):
            return options[choice - 1]

        typer.secho(
            "Invalid selection. Try again.",
            fg=typer.colors.RED,
        )


def choose_enum(
    enum_type: type[Enum],
    title: str,
):
    """
    Prompt the user to choose an enum value from a numbered list.
    """

    members = list(enum_type)

    selected = choose_option(
        [member.value for member in members],
        title,
    )

    for member in members:
        if member.value == selected:
            return member

    #
    # Unreachable: choose_option only returns supplied values.
    #

    raise ValueError(f"Invalid selection: {selected}")
