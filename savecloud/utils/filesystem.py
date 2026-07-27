"""
Filesystem helpers shared across SaveCloud.

These helpers contain no business logic. They exist so that every
component that copies save data does so with the same failure
semantics.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def replace_directory(
    source: Path,
    destination: Path,
) -> None:
    """
    Replace ``destination`` with a copy of ``source``.

    The copy is staged beside the destination and only swapped in once
    it has completed. A failure part way through therefore leaves the
    existing destination untouched rather than destroying it.
    """

    if not source.exists():
        raise FileNotFoundError(
            f"Source directory does not exist: {source}",
        )

    if not source.is_dir():
        raise NotADirectoryError(
            f"Source path is not a directory: {source}",
        )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    staging = destination.parent / f".{destination.name}.incoming"

    if staging.exists():
        shutil.rmtree(staging)

    shutil.copytree(
        source,
        staging,
    )

    previous = destination.parent / f".{destination.name}.previous"

    if previous.exists():
        shutil.rmtree(previous)

    try:
        if destination.exists():
            destination.rename(previous)

        staging.rename(destination)

    except OSError:
        #
        # Restore the original directory if the swap failed.
        #

        if not destination.exists() and previous.exists():
            previous.rename(destination)

        if staging.exists():
            shutil.rmtree(staging)

        raise

    if previous.exists():
        shutil.rmtree(previous)


def remove_directory(
    directory: Path,
) -> None:
    """
    Remove a directory if it exists.
    """

    if directory.exists():
        shutil.rmtree(directory)


def is_empty_directory(
    directory: Path,
) -> bool:
    """
    Return True if a directory exists and contains nothing.
    """

    return directory.is_dir() and not any(directory.iterdir())
