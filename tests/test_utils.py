"""
Tests for shared utilities.
"""

from __future__ import annotations

import pytest

from savecloud.utils.filesystem import (
    is_empty_directory,
    remove_directory,
    replace_directory,
)
from savecloud.utils.hashing import hash_directory

#
# Hashing
#


def test_identical_trees_hash_equal(tmp_path):

    left = tmp_path / "left"
    right = tmp_path / "right"

    for directory in (left, right):
        (directory / "nested").mkdir(parents=True)
        (directory / "save.dat").write_text("data", encoding="utf-8")
        (directory / "nested" / "more.dat").write_text("more", encoding="utf-8")

    assert hash_directory(left) == hash_directory(right)


def test_changed_contents_change_the_hash(tmp_path):

    directory = tmp_path / "save"

    directory.mkdir()

    (directory / "save.dat").write_text("before", encoding="utf-8")

    before = hash_directory(directory)

    (directory / "save.dat").write_text("after", encoding="utf-8")

    assert hash_directory(directory) != before


def test_renaming_a_file_changes_the_hash(tmp_path):
    """
    Content-only hashing would miss a rename; paths are included.
    """

    directory = tmp_path / "save"

    directory.mkdir()

    (directory / "a.dat").write_text("data", encoding="utf-8")

    before = hash_directory(directory)

    (directory / "a.dat").rename(directory / "b.dat")

    assert hash_directory(directory) != before


def test_missing_directory_hashes_like_an_empty_one(tmp_path):

    empty = tmp_path / "empty"

    empty.mkdir()

    assert hash_directory(tmp_path / "absent") == hash_directory(empty)


def test_noise_files_are_ignored(tmp_path):

    directory = tmp_path / "save"

    directory.mkdir()

    (directory / "save.dat").write_text("data", encoding="utf-8")

    before = hash_directory(directory)

    (directory / ".DS_Store").write_text("junk", encoding="utf-8")

    assert hash_directory(directory) == before


#
# Filesystem
#


def test_replace_directory_swaps_contents(tmp_path):

    source = tmp_path / "source"
    destination = tmp_path / "destination"

    source.mkdir()
    destination.mkdir()

    (source / "new.dat").write_text("new", encoding="utf-8")
    (destination / "old.dat").write_text("old", encoding="utf-8")

    replace_directory(source, destination)

    assert (destination / "new.dat").read_text(encoding="utf-8") == "new"
    assert not (destination / "old.dat").exists()


def test_replace_directory_creates_a_missing_destination(tmp_path):

    source = tmp_path / "source"

    source.mkdir()

    (source / "save.dat").write_text("data", encoding="utf-8")

    destination = tmp_path / "nested" / "destination"

    replace_directory(source, destination)

    assert (destination / "save.dat").read_text(encoding="utf-8") == "data"


def test_replace_directory_leaves_no_staging_behind(tmp_path):

    source = tmp_path / "source"
    destination = tmp_path / "destination"

    source.mkdir()

    (source / "save.dat").write_text("data", encoding="utf-8")

    replace_directory(source, destination)

    leftovers = [path.name for path in tmp_path.iterdir() if path.name.startswith(".")]

    assert leftovers == []


def test_replace_directory_preserves_destination_when_source_is_missing(tmp_path):

    destination = tmp_path / "destination"

    destination.mkdir()

    (destination / "keep.dat").write_text("keep", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        replace_directory(tmp_path / "absent", destination)

    assert (destination / "keep.dat").read_text(encoding="utf-8") == "keep"


def test_remove_directory_tolerates_a_missing_directory(tmp_path):

    remove_directory(tmp_path / "absent")


def test_is_empty_directory(tmp_path):

    empty = tmp_path / "empty"
    full = tmp_path / "full"

    empty.mkdir()
    full.mkdir()

    (full / "file").write_text("x", encoding="utf-8")

    assert is_empty_directory(empty)
    assert not is_empty_directory(full)
    assert not is_empty_directory(tmp_path / "absent")
