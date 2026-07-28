"""
Adapter for Windows games running under Proton.

Proton gives each game an emulated Windows drive under
`steamapps/compatdata/<app-id>/pfx`. Saves live somewhere inside it,
but Windows games follow no single convention - AppData/Roaming,
Documents/My Games, and Saved Games are all common, and plenty of
games invent their own.

So this adapter resolves the prefix automatically and then asks. A
wrong save directory silently synchronizes the wrong files, which is
worse than one extra question during registration.
"""

from __future__ import annotations

from pathlib import Path

import typer

from savecloud.adapters.base import BaseAdapter
from savecloud.utils import steam


class SteamProtonAdapter(BaseAdapter):
    """
    SaveCloud adapter for Proton games.
    """

    @staticmethod
    def display_name() -> str:
        """
        Human-readable adapter name.
        """

        return "Steam (Proton)"

    @staticmethod
    def identifier_name() -> str:
        """
        Name of the identifier this adapter expects.
        """

        return "Steam App ID"

    @staticmethod
    def locate_save(
        identifier: str,
    ) -> Path | None:
        """
        Locate a save directory for a Steam App ID.

        The identifier may be an App ID on its own, or an App ID and a
        path relative to the prefix's user directory, separated by a
        colon:

            2050650
            2050650:AppData/Roaming/MyGame

        The second form is what registration records once the user has
        chosen, so re-running discovery returns the same directory
        without asking again.
        """

        app_id, _, relative = identifier.partition(":")

        app_id = app_id.strip()

        if not app_id:
            return None

        user_directory = steam.prefix_user_directory(app_id)

        if user_directory is None:
            return None

        if relative:
            candidate = user_directory / relative.strip()

            return candidate if candidate.is_dir() else None

        return user_directory

    @staticmethod
    def validate_save(
        path: Path,
    ) -> bool:
        """
        Verify a discovered save directory.
        """

        return path.exists() and path.is_dir()

    @staticmethod
    def supports_auto_discovery() -> bool:
        """
        The prefix is found automatically; the save inside it is not.
        """

        return True

    @staticmethod
    def prompt_identifier() -> str:
        """
        Ask for a Steam App ID, then which directory holds the save.
        """

        from savecloud.utils.prompt import choose_option, prompt_required

        installed = steam.installed_apps()

        if not installed:
            typer.secho(
                "No installed Steam games were found. Check that Steam is "
                "installed and has downloaded at least one game.",
                fg=typer.colors.YELLOW,
            )

        app_id = prompt_required(
            "Steam App ID",
        ).strip()

        name = installed.get(app_id)

        if name:
            typer.secho(
                f"  {name}",
                fg=typer.colors.GREEN,
            )

        elif installed:
            typer.secho(
                "  That App ID is not installed on this device. "
                "Continuing anyway.",
                fg=typer.colors.YELLOW,
            )

        user_directory = steam.prefix_user_directory(app_id)

        if user_directory is None:
            typer.secho(
                "No Proton prefix exists for that App ID. Run the game "
                "once through Steam so Proton creates it, then register.",
                fg=typer.colors.RED,
            )

            return app_id

        candidates = steam.candidate_save_directories(app_id)

        if not candidates:
            typer.secho(
                "The Proton prefix exists but contains no obvious save "
                "directories. The whole user directory will be used, "
                "which may synchronize more than you want.",
                fg=typer.colors.YELLOW,
            )

            return app_id

        #
        # Present paths relative to the prefix. The absolute ones are
        # long enough to be unreadable in a list.
        #

        options = [
            str(path.relative_to(user_directory)) for path in candidates
        ]

        options.append("Enter a path manually")

        typer.echo()
        typer.echo(f"Save directories found in {user_directory}")

        chosen = choose_option(
            options,
            "Which one holds this game's saves?",
        )

        if chosen == "Enter a path manually":
            chosen = prompt_required(
                f"Path relative to {user_directory}",
            )

        return f"{app_id}:{chosen}"
