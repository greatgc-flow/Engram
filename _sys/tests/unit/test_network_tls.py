"""Windows trust-store integration for stdlib HTTPS clients."""
from __future__ import annotations

from unittest.mock import MagicMock

from _sys.core import network_tls


def test_add_windows_roots_loads_only_x509_certificates(monkeypatch):
    context = MagicMock()
    monkeypatch.setattr(network_tls.sys, "platform", "win32")

    def enum_certificates(store):
        assert store in {"ROOT", "CA"}
        return (
            [(b"first", "x509_asn", True), (b"bundle", "pkcs_7_asn", True)]
            if store == "ROOT"
            else [(b"second", "x509_asn", True)]
        )

    monkeypatch.setattr(
        network_tls.ssl,
        "enum_certificates",
        enum_certificates,
    )
    monkeypatch.setattr(
        network_tls.ssl,
        "DER_cert_to_PEM_cert",
        lambda value: f"PEM:{value.decode('ascii')}",
    )

    loaded = network_tls.add_windows_root_certificates(context)

    assert loaded == 2
    context.load_verify_locations.assert_called_once_with(
        cadata="PEM:first\nPEM:second"
    )


def test_add_windows_roots_is_noop_off_windows(monkeypatch):
    context = MagicMock()
    monkeypatch.setattr(network_tls.sys, "platform", "linux")

    assert network_tls.add_windows_root_certificates(context) == 0
    context.load_verify_locations.assert_not_called()


def test_add_python_ca_bundle_uses_pip_vendor_fallback(monkeypatch):
    context = MagicMock()

    def fake_import(name):
        if name == "certifi":
            raise ImportError(name)
        assert name == "pip._vendor.certifi"
        return type("Certifi", (), {"where": staticmethod(lambda: "ca.pem")})

    monkeypatch.setattr(network_tls, "import_module", fake_import)

    assert network_tls.add_python_ca_bundle(context) is True
    context.load_verify_locations.assert_called_once_with(cafile="ca.pem")


def test_install_urllib_platform_trust_is_idempotent(monkeypatch):
    original_context = MagicMock()

    def original_factory(*_args, **_kwargs):
        return original_context

    monkeypatch.setattr(network_tls.sys, "platform", "win32")
    monkeypatch.setattr(
        network_tls.ssl, "_create_default_https_context", original_factory
    )
    add_roots = MagicMock()
    add_bundle = MagicMock()
    monkeypatch.setattr(network_tls, "add_windows_root_certificates", add_roots)
    monkeypatch.setattr(network_tls, "add_python_ca_bundle", add_bundle)

    assert network_tls.install_urllib_platform_trust() is True
    installed_factory = network_tls.ssl._create_default_https_context
    assert network_tls.install_urllib_platform_trust() is False

    assert installed_factory() is original_context
    add_bundle.assert_called_once_with(original_context)
    add_roots.assert_called_once_with(original_context)
