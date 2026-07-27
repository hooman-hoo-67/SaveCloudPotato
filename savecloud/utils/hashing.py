"""
Content hashing helpers.

SaveCloud identifies save content by a checksum of the directory tree
rather than by modification time. Timestamps are unreliable across
devices, filesystems, and copy operations; content is not.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

#
# Files that never form part of a save's identity.
#

IGNORED_NAMES = {
    ".DS_Store",
    "Thumbs.db",
}

CHUNK_SIZE = 1024 * 1024


def hash_file(path: Path) -> str:
    """
    Return the SHA-256 digest of a single file.
    """

    digest = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            chunk = file.read(CHUNK_SIZE)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def hash_directory(directory: Path) -> str:
    """
    Return a stable checksum for an entire directory tree.

    The checksum covers each file's path relative to ``directory`` and
    its contents, so both renames and edits change the result. Empty
    directories do not contribute, keeping the checksum consistent
    across filesystems that treat them differently.

    A missing directory hashes to the digest of no content, which makes
    it comparable to an empty save without special-casing callers.
    """

    digest = hashlib.sha256()

    if not directory.exists():
        return digest.hexdigest()

    entries = []

    for path in directory.rglob("*"):

        if path.name in IGNORED_NAMES:
            continue

        if not path.is_file():
            continue

        entries.append(path)

    #
    # Sort by relative POSIX path so the result does not depend on
    # filesystem iteration order.
    #

    for path in sorted(
        entries,
        key=lambda item: item.relative_to(directory).as_posix(),
    ):
        relative = path.relative_to(directory).as_posix()

        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hash_file(path).encode("ascii"))
        digest.update(b"\0")

    return digest.hexdigest()
