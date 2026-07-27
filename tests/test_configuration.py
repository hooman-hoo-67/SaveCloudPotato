"""
Tests for installation-wide configuration.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from savecloud.models.installation_config import InstallationConfig
from savecloud.services.configuration import ConfigurationService
from savecloud.storage import LocalStorageBackend, StorageRegistry, SyncthingStorageBackend


def test_default_configuration_uses_local_backend():

    config = InstallationConfig()

    assert config.storage_backend == "local"
    assert isinstance(config.storage_root, Path)


def test_configuration_round_trips(tmp_path):

    config = InstallationConfig(
        storage_backend="syncthing",
        storage_root=tmp_path / "shared",
    )

    ConfigurationService.save(config)

    loaded = ConfigurationService.load()

    assert loaded.storage_backend == "syncthing"
    assert loaded.storage_root == tmp_path / "shared"


def test_string_storage_root_becomes_a_path():

    config = InstallationConfig(storage_root="~/somewhere")

    assert isinstance(config.storage_root, Path)
    assert "~" not in str(config.storage_root)


def test_load_falls_back_to_defaults_when_missing(monkeypatch, tmp_path):

    monkeypatch.setenv("SAVECLOUD_HOME", str(tmp_path / "empty"))

    assert not ConfigurationService.exists()

    assert ConfigurationService.load().storage_backend == "local"


def test_load_falls_back_to_defaults_when_corrupt():

    ConfigurationService.path().write_text("{not json", encoding="utf-8")

    #
    # A damaged config must not make SaveCloud unusable.
    #

    assert ConfigurationService.load().storage_backend == "local"


def test_unknown_keys_are_ignored():

    ConfigurationService.path().write_text(
        json.dumps(
            {
                "storage_backend": "local",
                "storage_root": "/tmp/x",
                "from_a_newer_version": True,
            }
        ),
        encoding="utf-8",
    )

    assert ConfigurationService.load().storage_backend == "local"


def test_set_backend_persists():

    ConfigurationService.set_backend("syncthing")

    assert ConfigurationService.load().storage_backend == "syncthing"


def test_set_backend_rejects_unknown_backend():

    with pytest.raises(ValueError):
        ConfigurationService.set_backend("dropbox")

    assert ConfigurationService.load().storage_backend == "local"


def test_set_root_persists(tmp_path):

    ConfigurationService.set_root(tmp_path / "elsewhere")

    assert ConfigurationService.load().storage_root == tmp_path / "elsewhere"


def test_initialize_is_idempotent(tmp_path):

    ConfigurationService.set_root(tmp_path / "kept")

    ConfigurationService.initialize()

    assert ConfigurationService.load().storage_root == tmp_path / "kept"


def test_registry_resolves_the_configured_backend():

    assert StorageRegistry.resolve() is LocalStorageBackend

    ConfigurationService.set_backend("syncthing")

    assert StorageRegistry.resolve() is SyncthingStorageBackend


def test_registry_rejects_an_unregistered_backend():

    ConfigurationService.save(
        InstallationConfig(storage_backend="nonexistent"),
    )

    with pytest.raises(RuntimeError, match="Unknown storage backend"):
        StorageRegistry.resolve()
