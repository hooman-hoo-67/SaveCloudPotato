"""
Finding the machine's certificate authorities.

A frozen build carries OpenSSL with the certificate paths of whichever
machine built it compiled in. SaveCloud's AppImage is built on Ubuntu,
where they are `/usr/lib/ssl`; SteamOS is Arch, where that directory
does not exist. So the AppImage started on a Steam Deck with no
trusted authorities at all, and every HTTPS request failed.

It failed misleadingly, too. An empty trust store does not report
itself as empty - when a server sends a chain ending in a root the
client does not trust, OpenSSL says:

    certificate verify failed: self-signed certificate in certificate
    chain

which reads exactly like a network intercepting TLS, and was diagnosed
as one. The same message appears with no interception whatever if the
trust store cannot be found, which is what a Deck was really seeing.

So the paths are checked, and if they lead nowhere the usual locations
are searched instead. The system's own store rather than a bundled
copy: a bundled one is a snapshot that goes stale, and it would ignore
an authority the user added deliberately - which is the one case where
being wrong is worst.
"""

from __future__ import annotations

import os
import ssl
from pathlib import Path

#
# Where distributions keep a concatenated bundle. Ordered by how much
# of the desktop Linux world each covers, so the common answer is
# usually the first one tried.
#

BUNDLES = (
    #
    # Debian, Ubuntu, Arch and SteamOS all end up here, the last two
    # through a symlink into /etc/ca-certificates.
    #
    "/etc/ssl/certs/ca-certificates.crt",
    #
    # Fedora, RHEL, CentOS.
    #
    "/etc/pki/tls/certs/ca-bundle.crt",
    #
    # openSUSE.
    #
    "/etc/ssl/ca-bundle.pem",
    #
    # Alpine, and the path macOS uses when Homebrew's OpenSSL is
    # involved.
    #
    "/etc/ssl/cert.pem",
    #
    # Arch's own extracted bundle, in case the symlink above is
    # missing.
    #
    "/etc/ca-certificates/extracted/tls-ca-bundle.pem",
)

#
# Directories of individually hashed certificates, used when no single
# bundle file exists.
#

DIRECTORIES = (
    "/etc/ssl/certs",
    "/etc/pki/tls/certs",
)


def has_trust_store() -> bool:
    """
    Return whether OpenSSL's compiled-in paths lead anywhere real.
    """

    paths = ssl.get_default_verify_paths()

    for candidate in (paths.cafile, paths.openssl_cafile):
        if candidate and Path(candidate).is_file():
            return True

    for candidate in (paths.capath, paths.openssl_capath):
        if candidate and Path(candidate).is_dir():
            #
            # A directory that exists but holds nothing is the same as
            # no directory, and is what an unpacked build can leave
            # behind.
            #
            try:
                if any(Path(candidate).iterdir()):
                    return True

            except OSError:
                continue

    return False


def find_trust_store() -> tuple[str | None, str | None]:
    """
    Return the first usable bundle and directory on this machine.
    """

    bundle = next(
        (path for path in BUNDLES if Path(path).is_file()),
        None,
    )

    directory = next(
        (path for path in DIRECTORIES if Path(path).is_dir()),
        None,
    )

    return bundle, directory


def ensure_trust_store() -> bool:
    """
    Point OpenSSL at this machine's authorities if it has none.

    Returns whether anything was changed. Does nothing when the
    compiled-in paths already work, and nothing when the environment
    already names a store - someone who set `SSL_CERT_FILE` by hand,
    to trust a proxy's authority for instance, meant it.
    """

    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return False

    if has_trust_store():
        return False

    bundle, directory = find_trust_store()

    if bundle is None and directory is None:
        #
        # Nothing to be done. Left alone rather than guessed at, so
        # the failure stays a certificate error rather than becoming a
        # missing-file error somewhere less obvious.
        #

        return False

    if bundle is not None:
        os.environ["SSL_CERT_FILE"] = bundle

    if directory is not None:
        os.environ["SSL_CERT_DIR"] = directory

    return True
