"""
What a game ID is allowed to be.

An ID is not just a label - it names a directory in the library, in the
registry, in every storage backend, and a lock file in the cache. So an
ID containing a path separator does not name a game badly, it names a
different place.

That was reachable. `register` prompts for an ID and wrote whatever it
was given: `pokemon black/white` registered without complaint, put its
manifest one directory deeper than anything looks, and then never
appeared in `list` again - which also meant it could not be removed,
because `unregister` takes an ID it can no longer show you. `../name`
escaped the library directory entirely.

Checked when a game is registered rather than when one is loaded. A
library that already contains such an entry should still open; refusing
to read it would turn a bad name into unreachable save data.
"""

from __future__ import annotations

import re

#
# Characters that are not legal in a filename on Windows, plus the two
# path separators. SaveCloud's own platform support is Linux, but a
# library travels: an ID chosen on a Deck has to be creatable wherever
# the same account synchronizes next.
#

FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

#
# Windows refuses these as filenames whatever the extension.
#

RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{digit}" for digit in range(1, 10)),
    *(f"lpt{digit}" for digit in range(1, 10)),
}

MAX_LENGTH = 100


class InvalidGameIdError(ValueError):
    """
    Raised when an ID cannot be used as a directory name.
    """


def validate_game_id(game_id: str) -> str:
    """
    Return the ID, or explain why it cannot be used.

    Raises
    ------
    InvalidGameIdError
        With a message meant to be shown to whoever typed it.
    """

    if not game_id or not game_id.strip():
        raise InvalidGameIdError("A game ID cannot be empty.")

    if game_id != game_id.strip():
        raise InvalidGameIdError(
            "A game ID cannot begin or end with a space."
        )

    if len(game_id) > MAX_LENGTH:
        raise InvalidGameIdError(
            f"A game ID cannot be longer than {MAX_LENGTH} characters."
        )

    found = FORBIDDEN.search(game_id)

    if found:
        character = found.group()

        #
        # Naming the character matters more than listing the rule. The
        # usual way to arrive here is a title that genuinely contains a
        # slash, and "/ cannot be used" is the whole explanation.
        #

        shown = (
            repr(character)
            if character.isprintable()
            else "a control character"
        )

        raise InvalidGameIdError(
            f"A game ID cannot contain {shown}, because it names a "
            f"folder. Try a hyphen instead."
        )

    #
    # `.` and `..` are directory entries that already mean something.
    #

    if set(game_id) == {"."}:
        raise InvalidGameIdError('A game ID cannot be "." or "..".')

    if game_id.endswith("."):
        raise InvalidGameIdError("A game ID cannot end with a full stop.")

    if game_id.lower() in RESERVED:
        raise InvalidGameIdError(
            f'"{game_id}" is a reserved name on Windows and cannot be '
            f"used as a folder."
        )

    return game_id
