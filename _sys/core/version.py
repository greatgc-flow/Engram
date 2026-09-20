import json
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


VERSION_INFO = load_version_info()
VERSION = VERSION_INFO.get("version", "unknown")
WINGET_SCHEMA_VERSION = VERSION_INFO.get("winget_schema_version", "unknown")
