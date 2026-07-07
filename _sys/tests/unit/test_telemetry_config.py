"""snapshot.telemetry_config — config loader with defaults + type-guard.

Ensures the MECE constants (token-session-policy-design-2026-07-08) load from
_sys/ai/telemetry-config.json, degrade to documented defaults on a missing/typo'd
key, and never crash on a malformed file.
"""
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import snapshot


def _reset_cache():
    snapshot._TELEMETRY_CACHE["cfg"] = None


def test_defaults_present_and_typed():
    _reset_cache()
    cfg = snapshot.telemetry_config()
    assert cfg["ttl"]["snapshot_sec"] == 60
    assert cfg["display"]["crit_frac"] == 0.90
    assert cfg["watch"]["min_interval_sec"] == 2
    assert isinstance(cfg["watch"]["sync_output"], str)


def test_override_wins_but_wrong_type_falls_back(monkeypatch, tmp_path):
    bad = tmp_path / "telemetry-config.json"
    bad.write_text('{"ttl": {"snapshot_sec": 15, "local_sec": "oops"}}', encoding="utf-8")
    monkeypatch.setattr(snapshot, "SYS_DIR", tmp_path.parent)
    # point the loader at our temp file by faking the ai dir layout
    (tmp_path.parent / "ai").mkdir(exist_ok=True)
    (tmp_path.parent / "ai" / "telemetry-config.json").write_text(
        '{"ttl": {"snapshot_sec": 15, "local_sec": "oops"}}', encoding="utf-8")
    _reset_cache()
    cfg = snapshot.telemetry_config()
    assert cfg["ttl"]["snapshot_sec"] == 15      # valid override applied
    assert cfg["ttl"]["local_sec"] == 5          # wrong-type -> documented default
    _reset_cache()


def test_malformed_file_degrades_to_defaults(monkeypatch, tmp_path):
    (tmp_path.parent / "ai").mkdir(exist_ok=True)
    (tmp_path.parent / "ai" / "telemetry-config.json").write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(snapshot, "SYS_DIR", tmp_path.parent)
    _reset_cache()
    cfg = snapshot.telemetry_config()
    assert cfg["ttl"]["snapshot_sec"] == 60      # never crashes; defaults
    _reset_cache()
