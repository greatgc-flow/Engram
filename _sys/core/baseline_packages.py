"""Managed baseline: pip distribution specifications and import-module names."""

BASELINE_PACKAGES = (
    ("filelock", "filelock"),
    ("pywinpty", "winpty"),
    ("psutil", "psutil"),
    ("pydantic", "pydantic"),
)


def runtime_pins(path=None):
    """Read the five direct fresh-install requirements; reject partial manifests."""
    import re
    from pathlib import Path
    path = Path(path) if path is not None else Path(__file__).resolve().parents[1] / "defaults/requirements-runtime.txt"
    pins = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.fullmatch(r"([a-z][a-z0-9-]*)==([0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?)", line)
            if not match or match[1] in pins:
                raise ValueError("malformed or duplicate pin")
            pins[match[1]] = line
        if set(pins) != {name for name, _ in BASELINE_PACKAGES} | {"virtualenv"}:
            raise ValueError("expected exactly five baseline pins")
    except (OSError, ValueError) as exc:
        raise ValueError(f"Invalid runtime manifest {path}: {exc}") from exc
    return pins
