"""
Provider credential storage.

Tokens live in `providers/<name>.json` inside the SaveCloud home
directory, which is never synchronized. A refresh token grants access
to someone's cloud storage, so replicating it to every device the way
the registry is replicated would be a poor trade.

Files are written with owner-only permissions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from savecloud.config.constants import provider_dir


class CredentialService:
    """
    Load and persist per-provider credentials.
    """

    @staticmethod
    def path(provider: str) -> Path:
        """
        Return the credential file path for a provider.
        """

        return provider_dir() / f"{provider.lower()}.json"

    @staticmethod
    def exists(provider: str) -> bool:
        """
        Return True if credentials are stored for a provider.
        """

        return CredentialService.path(provider).exists()

    @staticmethod
    def load(provider: str) -> dict:
        """
        Load a provider's credentials.

        Returns an empty mapping when nothing is stored or the file
        cannot be read. A backend is expected to report itself
        unavailable rather than crash.
        """

        path = CredentialService.path(provider)

        if not path.exists():
            return {}

        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)

        except (json.JSONDecodeError, OSError):
            return {}

        return data if isinstance(data, dict) else {}

    @staticmethod
    def save(
        provider: str,
        credentials: dict,
    ) -> None:
        """
        Store a provider's credentials with owner-only permissions.
        """

        directory = provider_dir()

        directory.mkdir(parents=True, exist_ok=True)

        path = CredentialService.path(provider)

        #
        # Create the file before writing so the secret is never briefly
        # readable by anyone else.
        #

        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )

        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(credentials, file, indent=4)

    @staticmethod
    def update(
        provider: str,
        **values,
    ) -> dict:
        """
        Merge values into a provider's stored credentials.
        """

        credentials = CredentialService.load(provider)

        credentials.update(values)

        CredentialService.save(provider, credentials)

        return credentials

    @staticmethod
    def delete(provider: str) -> None:
        """
        Remove a provider's credentials.
        """

        path = CredentialService.path(provider)

        if path.exists():
            path.unlink()
