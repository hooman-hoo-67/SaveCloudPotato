"""
Finding the machine's certificate authorities.

A frozen build carries the certificate paths of the machine that built
it. SaveCloud's AppImage is built on Ubuntu, where they are
`/usr/lib/ssl`; SteamOS is Arch, where that does not exist. So the
AppImage ran on a Steam Deck with no trusted authorities and every
HTTPS request failed - Dropbox authorization among them.

The message it failed with is the reason this has its own file:

    certificate verify failed: self-signed certificate in certificate
    chain

An empty trust store produces that, with nothing intercepting
anything, because a chain ending in an untrusted root looks
self-signed from the inside. It was read as a network doing TLS
inspection, and it was not.
"""

from __future__ import annotations

import ssl

import pytest

from savecloud.utils import certificates


class Paths:
    """
    Stand in for what OpenSSL was compiled to look for.
    """

    def __init__(self, cafile=None, capath=None) -> None:
        self.cafile = cafile
        self.openssl_cafile = cafile
        self.capath = capath
        self.openssl_capath = capath


@pytest.fixture
def clean(monkeypatch):
    """
    No inherited environment, so each test starts from nothing.
    """

    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)


def compiled_for(monkeypatch, cafile=None, capath=None) -> None:
    """
    Pretend OpenSSL was compiled to look at these paths.
    """

    monkeypatch.setattr(
        ssl,
        "get_default_verify_paths",
        lambda: Paths(cafile, capath),
    )


#
# Noticing
#


def test_a_missing_store_is_noticed(monkeypatch, clean):
    """
    What a Deck sees: paths from the machine that built the AppImage.
    """

    compiled_for(
        monkeypatch,
        cafile="/usr/lib/ssl/cert.pem",
        capath="/usr/lib/ssl/certs",
    )

    monkeypatch.setattr(certificates.Path, "is_file", lambda self: False)
    monkeypatch.setattr(certificates.Path, "is_dir", lambda self: False)

    assert certificates.has_trust_store() is False


def test_a_real_bundle_is_enough(monkeypatch, clean, tmp_path):

    bundle = tmp_path / "ca-certificates.crt"

    bundle.write_text("-----BEGIN CERTIFICATE-----\n", encoding="utf-8")

    compiled_for(monkeypatch, cafile=str(bundle))

    assert certificates.has_trust_store() is True


def test_an_empty_directory_is_not_a_store(monkeypatch, clean, tmp_path):
    """
    A directory that exists and holds nothing trusts nothing.
    """

    empty = tmp_path / "certs"

    empty.mkdir()

    compiled_for(monkeypatch, capath=str(empty))

    assert certificates.has_trust_store() is False


def test_a_populated_directory_is_a_store(monkeypatch, clean, tmp_path):

    directory = tmp_path / "certs"

    directory.mkdir()

    (directory / "abc123.0").write_text("cert", encoding="utf-8")

    compiled_for(monkeypatch, capath=str(directory))

    assert certificates.has_trust_store() is True


#
# Repairing
#


def test_a_missing_store_is_replaced(monkeypatch, clean, tmp_path):

    bundle = tmp_path / "ca-certificates.crt"

    bundle.write_text("certs", encoding="utf-8")

    compiled_for(monkeypatch, cafile="/nowhere/cert.pem")

    monkeypatch.setattr(certificates, "BUNDLES", (str(bundle),))
    monkeypatch.setattr(certificates, "DIRECTORIES", ())

    import os

    assert certificates.ensure_trust_store() is True

    assert os.environ["SSL_CERT_FILE"] == str(bundle)


def test_a_working_store_is_left_alone(monkeypatch, clean, tmp_path):
    """
    Nothing to fix, so nothing is touched.
    """

    import os

    bundle = tmp_path / "ca-certificates.crt"

    bundle.write_text("certs", encoding="utf-8")

    compiled_for(monkeypatch, cafile=str(bundle))

    assert certificates.ensure_trust_store() is False

    assert "SSL_CERT_FILE" not in os.environ


def test_a_deliberate_setting_is_never_overridden(monkeypatch, tmp_path):
    """
    Someone who set SSL_CERT_FILE by hand meant it.

    Trusting a proxy's authority is done exactly this way, and
    replacing it with the system store would undo the thing they set
    out to do.
    """

    import os

    monkeypatch.setenv("SSL_CERT_FILE", "/their/own/bundle.pem")
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)

    compiled_for(monkeypatch, cafile="/nowhere/cert.pem")

    assert certificates.ensure_trust_store() is False

    assert os.environ["SSL_CERT_FILE"] == "/their/own/bundle.pem"


def test_a_machine_with_nothing_is_left_as_it_was(monkeypatch, clean):
    """
    Better a certificate error than a missing-file error elsewhere.
    """

    import os

    compiled_for(monkeypatch, cafile="/nowhere/cert.pem")

    monkeypatch.setattr(certificates, "BUNDLES", ("/also/nowhere.pem",))
    monkeypatch.setattr(certificates, "DIRECTORIES", ("/nowhere/certs",))

    assert certificates.ensure_trust_store() is False

    assert "SSL_CERT_FILE" not in os.environ


def test_the_search_prefers_the_common_location(monkeypatch, clean, tmp_path):
    """
    Debian, Ubuntu, Arch and SteamOS all land on the same file.
    """

    first = tmp_path / "ca-certificates.crt"

    second = tmp_path / "ca-bundle.crt"

    for path in (first, second):
        path.write_text("certs", encoding="utf-8")

    monkeypatch.setattr(
        certificates,
        "BUNDLES",
        (str(first), str(second)),
    )

    bundle, _ = certificates.find_trust_store()

    assert bundle == str(first)
