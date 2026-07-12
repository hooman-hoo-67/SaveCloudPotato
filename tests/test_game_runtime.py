"""
Test GameRuntime state helper methods.

Run with:

python tests/test_game_runtime.py
"""

from savecloud.models.game import (
    GameRuntime,
    SyncStatus,
)


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:

    #
    # Create Runtime
    #

    section("TEST 1 - CREATE RUNTIME")

    runtime = GameRuntime()

    assert runtime.current_version == 0
    assert runtime.status == SyncStatus.UNKNOWN
    assert runtime.pending_upload is False
    assert runtime.last_device is None
    assert runtime.last_sync is None
    assert runtime.last_error is None
    assert runtime.created_at is not None

    print("✓ Runtime created")

    #
    # Pending
    #

    section("TEST 2 - MARK PENDING")

    runtime.mark_pending()

    assert runtime.status == SyncStatus.PENDING
    assert runtime.pending_upload is True
    assert runtime.last_error is None

    print("✓ Pending state verified")

    #
    # Synced
    #

    section("TEST 3 - MARK SYNCED")

    runtime.mark_synced(
        "device-123",
    )

    assert runtime.status == SyncStatus.SYNCED
    assert runtime.pending_upload is False
    assert runtime.last_device == "device-123"
    assert runtime.last_sync is not None
    assert runtime.last_error is None

    print("✓ Synced state verified")

    #
    # Error
    #

    section("TEST 4 - MARK ERROR")

    runtime.mark_error(
        "Upload failed",
    )

    assert runtime.status == SyncStatus.ERROR
    assert runtime.last_error == "Upload failed"

    #
    # Upload should still be pending after an error.
    #

    assert runtime.pending_upload is False

    print("✓ Error state verified")

    #
    # Conflict
    #

    section("TEST 5 - MARK CONFLICT")

    runtime.mark_conflict()

    assert runtime.status == SyncStatus.CONFLICT

    #
    # Conflict should not change other runtime fields.
    #

    assert runtime.last_device == "device-123"
    assert runtime.last_sync is not None
    assert runtime.last_error == "Upload failed"

    print("✓ Conflict state verified")

    #
    # Complete
    #

    section("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
