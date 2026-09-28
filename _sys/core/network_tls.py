"""TLS trust integration for Python's stdlib HTTP clients on Windows.

The embeddable Python distribution does not always expose the Windows root
certificate store to OpenSSL.  Keep certificate verification enabled and add
the machine's trusted X.509 roots to the context urllib creates.
"""
from __future__ import annotations

import ssl
import sys
from importlib import import_module
from typing import Any


_FACTORY_MARKER = "_engram_windows_root_trust"


def add_python_ca_bundle(context: ssl.SSLContext) -> bool:
    """Load certifi's public CA bundle when available.

    Fresh embeddable-Python installs always bootstrap pip before importing this
    module.  Pip vendors certifi, so it provides a safe fallback even when a
    standalone certifi package has not been installed.
    """

    for module_name in ("certifi", "pip._vendor.certifi"):
        try:
            certifi = import_module(module_name)
            context.load_verify_locations(cafile=certifi.where())
            return True
        except (ImportError, AttributeError, OSError, ssl.SSLError, ValueError):
            continue
    return False


def add_windows_root_certificates(context: ssl.SSLContext) -> int:
    """Add usable certificates from Windows ROOT and CA stores to *context*.

    Returns the number of X.509 certificates loaded.  Non-Windows hosts and
    Python builds without ``enum_certificates`` retain their normal defaults.
    """

    if sys.platform != "win32":
        return 0
    enum_certificates = getattr(ssl, "enum_certificates", None)
    if enum_certificates is None:
        return 0

    pem_roots: list[str] = []
    for store_name in ("ROOT", "CA"):
        try:
            certificates = enum_certificates(store_name)
        except (OSError, ssl.SSLError):
            continue
        for certificate, encoding, _trust in certificates:
            if encoding == "x509_asn":
                pem_roots.append(ssl.DER_cert_to_PEM_cert(certificate))
    if not pem_roots:
        return 0
    try:
        context.load_verify_locations(cadata="\n".join(pem_roots))
    except (OSError, ssl.SSLError, ValueError):
        return 0
    return len(pem_roots)


def install_urllib_platform_trust() -> bool:
    """Make urllib's default HTTPS context include the Windows root store.

    The wrapper is idempotent even if this module is imported through both the
    ``core`` and ``_sys.core`` package paths.  It augments trust; it never turns
    off hostname or certificate verification.
    """

    if sys.platform != "win32":
        return False
    current_factory: Any = ssl._create_default_https_context
    if getattr(current_factory, _FACTORY_MARKER, False):
        return False

    def engram_https_context(*args: Any, **kwargs: Any) -> ssl.SSLContext:
        context = current_factory(*args, **kwargs)
        add_python_ca_bundle(context)
        add_windows_root_certificates(context)
        return context

    setattr(engram_https_context, _FACTORY_MARKER, True)
    ssl._create_default_https_context = engram_https_context
    return True
