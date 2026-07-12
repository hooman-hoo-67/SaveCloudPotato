"""
Test LaunchService.

Run with:

python tests/test_launch.py
"""

from __future__ import annotations

from savecloud.models.device_profile import DeviceProfile
from savecloud.services.launch import LaunchService


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def main() -> None:

    #
    # Create profile
    #

    section("TEST 1 - CREATE PROFILE")

    profile = DeviceProfile(
        device_id="device-test",
        device_name="Test Device",
        game_id="launch-test",
        working_save_path="/tmp",
        launch_command="sleep 2",
    )

    print("✓ Profile created")

    #
    # Launch
    #

    section("TEST 2 - LAUNCH")

    process = LaunchService.launch(
        profile,
    )

    assert process.pid is not None
    assert process.pid > 0

    print(f"✓ Process started (PID {process.pid})")

    #
    # Running
    #

    section("TEST 3 - VERIFY RUNNING")

    assert LaunchService.is_running(
        process,
    )

    print("✓ Process is running")

    #
    # Wait
    #

    section("TEST 4 - WAIT")

    exit_code = LaunchService.wait(
        process,
    )

    assert exit_code == 0

    print("✓ Process exited successfully")

    #
    # Finished
    #

    section("TEST 5 - VERIFY EXIT")

    assert not LaunchService.is_running(
        process,
    )

    print("✓ Process is no longer running")

    #
    # Complete
    #

    section("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
