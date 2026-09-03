import json
from pathlib import Path

def load_version_info() -> dict:
    version_file = Path(__file__).parent / "version.json"
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"version": "3.0.0", "winget_schema_version": "1.6.0"}

VERSION_INFO = load_version_info()
VERSION = VERSION_INFO.get("version", "3.0.0")
WINGET_SCHEMA_VERSION = VERSION_INFO.get("winget_schema_version", "1.6.0")
