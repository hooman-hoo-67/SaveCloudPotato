"""
Test installation configuration.
"""

from __future__ import annotations

from pathlib import Path
import shutil

from savecloud.models.installation_config import (
    InstallationConfig,
)
from savecloud.services.configuration import (
    ConfigurationService,
)


def cleanup() -> None:
    """
    Remove any existing configuration.
    """

    config = ConfigurationService.CONFIG_FILE

    if config.exists():
        config.unlink()

    if config.parent.exists():
        shutil.rmtree(
            config.parent,
        )


def main() -> None:
    """
    Run configuration tests.
    """

    cleanup()

    print()
    print("=" * 70)
    print("TEST 1 - DEFAULT CONFIGURATION")
    print("=" * 70)

    config = ConfigurationService.default()

    assert config.storage_backend == "local"

    assert config.storage_root == Path.home() / "SaveCloudRemote"

    print("✓ Default configuration verified")

    print()
    print("=" * 70)
    print("TEST 2 - SAVE CONFIGURATION")
    print("=" * 70)

    config = InstallationConfig(
        storage_backend="syncthing",
        storage_root=Path(
            "/tmp/savecloud",
        ),
    )

    ConfigurationService.save(
        config,
    )

    assert ConfigurationService.exists()

    print("✓ Configuration saved")

    print()
    print("=" * 70)
    print("TEST 3 - LOAD CONFIGURATION")
    print("=" * 70)

    loaded = ConfigurationService.load()

    assert loaded.storage_backend == "syncthing"

    assert loaded.storage_root == Path(
        "/tmp/savecloud",
    )

    print("✓ Configuration loaded")

    print()
    print("=" * 70)
    print("TEST 4 - DEFAULT FALLBACK")
    print("=" * 70)

    cleanup()

    loaded = ConfigurationService.load()

    assert loaded.storage_backend == "local"

    assert loaded.storage_root == Path.home() / "SaveCloudRemote"

    print("✓ Default configuration returned")

    cleanup()

    print()
    print("=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()
