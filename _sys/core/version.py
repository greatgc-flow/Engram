import json
import re
import sys
from pathlib import Path

_CORE_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CORE_DIR.parent

sys.path.insert(0, str(_CORE_DIR))
from root import bootstrap_root_package  # noqa: E402
bootstrap_root_package(_SYS_DIR)


def load_version_info(version_file: Path | None = None) -> dict:
    if version_file is None:
        version_file = _CORE_DIR / "version.json"
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except Exception:
        return {}


def is_newer_release(candidate: str, current: str) -> bool:
    """Return whether a stable ``X.Y.Z`` candidate is newer than current.

    Engram publishes numeric stable releases only. Unknown current versions may
    be repaired by a valid release, while malformed candidates are never offered
    as updates.
    """

    def parse(value: str) -> tuple[int, int, int] | None:
        match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(value).strip())
        if match is None:
            return None
        return tuple(int(part) for part in match.groups())

    candidate_parts = parse(candidate)
    if candidate_parts is None:
        return False
    current_parts = parse(current)
    return current_parts is None or candidate_parts > current_parts


VERSION_INFO = load_version_info()
VERSION = VERSION_INFO.get("version", "unknown")
WINGET_SCHEMA_VERSION = VERSION_INFO.get("winget_schema_version", "unknown")
