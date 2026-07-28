"""
Minimal reader for Valve's text KeyValues format.

Steam describes its libraries and installed applications in this
format. Only reading is supported, and only the subset Steam actually
writes: quoted keys and values, nested braces, and line comments.

Binary VDF - which is what shortcuts.vdf uses - is a different format
and is not handled here.
"""

from __future__ import annotations

from pathlib import Path

#
# Escape sequences Valve emits inside quoted strings.
#

ESCAPES = {
    "n": "\n",
    "t": "\t",
    "\\": "\\",
    '"': '"',
}


def _unescape(text: str) -> str:
    """
    Resolve backslash escapes in a quoted string.
    """

    if "\\" not in text:
        return text

    result: list[str] = []

    index = 0

    while index < len(text):

        character = text[index]

        if character == "\\" and index + 1 < len(text):
            following = text[index + 1]

            result.append(ESCAPES.get(following, following))

            index += 2

            continue

        result.append(character)

        index += 1

    return "".join(result)


def _tokenize(text: str) -> list[str]:
    """
    Split VDF source into quoted strings and braces.
    """

    tokens: list[str] = []

    index = 0

    length = len(text)

    while index < length:

        character = text[index]

        #
        # Whitespace
        #

        if character.isspace():
            index += 1
            continue

        #
        # Line comment
        #

        if text.startswith("//", index):
            newline = text.find("\n", index)

            index = length if newline == -1 else newline + 1

            continue

        #
        # Braces
        #

        if character in "{}":
            tokens.append(character)
            index += 1
            continue

        #
        # Quoted string
        #

        if character == '"':
            index += 1

            start = index

            while index < length:

                if text[index] == "\\":
                    index += 2
                    continue

                if text[index] == '"':
                    break

                index += 1

            tokens.append(_unescape(text[start:index]))

            index += 1

            continue

        #
        # Unquoted token. Steam rarely writes these, but tolerate them
        # rather than losing the rest of the file.
        #

        start = index

        while index < length and not text[index].isspace() and text[index] not in '{}"':
            index += 1

        tokens.append(text[start:index])

    return tokens


def loads(text: str) -> dict:
    """
    Parse VDF source into nested dictionaries.

    Malformed input yields whatever could be read rather than raising.
    Steam files are written by another program; a parse failure should
    degrade to "this library was not found", not crash SaveCloud.
    """

    tokens = _tokenize(text)

    root: dict = {}

    #
    # Stack of dictionaries currently being filled.
    #

    stack: list[dict] = [root]

    pending_key: str | None = None

    for token in tokens:

        if token == "{":
            #
            # A brace with no preceding key is meaningless; ignore it.
            #

            if pending_key is None:
                continue

            child: dict = {}

            stack[-1][pending_key] = child

            stack.append(child)

            pending_key = None

            continue

        if token == "}":
            if len(stack) > 1:
                stack.pop()

            pending_key = None

            continue

        if pending_key is None:
            pending_key = token
            continue

        stack[-1][pending_key] = token

        pending_key = None

    return root


def load(path: Path) -> dict:
    """
    Parse a VDF file.

    Returns an empty mapping if the file cannot be read.
    """

    try:
        return loads(path.read_text(encoding="utf-8", errors="replace"))

    except OSError:
        return {}
