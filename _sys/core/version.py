import json
from pathlib import Path

def load_version_info(version_file: Path | None = None) -> dict:
    if version_file is None:
        version_file = Path(__file__).parent / "version.json"
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
