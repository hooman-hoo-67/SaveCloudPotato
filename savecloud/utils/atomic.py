"""
Writing a document without the chance of half of one.

`open("w")` truncates before it writes. Between those two moments the
file is empty, and a process that dies in that window leaves nothing
where the state used to be.

That window is reachable. Steam escalates SIGTERM to SIGKILL during
shutdown, and SIGKILL cannot be caught - so a session ending while
`runtime.json` is being written is exactly the case this exists for.
Losing that file loses `last_sync_checksum`, which is the ancestor
conflict detection compares against: the safety mechanism, not a
convenience.

So the new contents are written beside the target and renamed over it.
A rename within a filesystem is atomic, so a reader sees either the
old document or the new one and never a partial one.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

#
# Whether to force the contents to disk before renaming.
#
# The rename alone survives the failure this exists for: a process
# killed mid-write. `fsync` additionally survives the machine losing
# power, which is rarer and considerably more expensive - it is a real
# disk round trip per document.
#
# The test suite writes thousands of documents to a temporary
# directory it is about to delete, and cares about none of that, so it
# turns this off. Nothing else should.
#

DURABLE = True


def write_text(path: Path, contents: str, mode: int | None = None) -> None:
    """
    Replace a file's contents, atomically.

    Parameters
    ----------
    path
        File to write. Its parent must exist.
    contents
        What the file should contain afterwards.
    mode
        Permissions for the result. Needed because a temporary file is
        created private, and a document that should stay private must
        not become readable on the way through.
    """

    directory = path.parent

    #
    # The temporary file has to share the filesystem: a rename across
    # one is not atomic, and on Linux is not a rename at all.
    #

    handle, temporary = tempfile.mkstemp(
        dir=directory,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )

    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(contents)

            #
            # Flushed and synced before the rename. Without this the
            # rename can reach the disk before the contents do, which
            # after a power loss leaves a file that exists and is
            # empty - the failure this is meant to prevent, arrived at
            # by a different route.
            #

            if DURABLE:
                file.flush()

                os.fsync(file.fileno())

        os.chmod(temporary, mode if mode is not None else 0o644)

        os.replace(temporary, path)

    except BaseException:
        #
        # Leaving a stray temporary file would be untidy; leaving it
        # while also failing would be worse.
        #

        try:
            os.unlink(temporary)

        except OSError:
            pass

        raise


def write_json(path: Path, data: Any, mode: int | None = None) -> None:
    """
    Replace a file with a JSON document, atomically.
    """

    write_text(path, json.dumps(data, indent=4) + "\n", mode=mode)
