"""check_policy_constants (CHK-CONST) — no-hardcoding / policy-drift guard.

Proves the live tree is clean and that each of the three sub-checks fires on a
representative violation (design 2026-07-08 §2).
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # _sys/
GUARD = ROOT / "checks" / "check_policy_constants.py"


def _mod():
    spec = importlib.util.spec_from_file_location("check_policy_constants_ut", GUARD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_live_tree_is_clean():
    assert _mod().run() == []


def test_config_sourced_scan_flags_hardcode(monkeypatch, tmp_path):
    m = _mod()
    fake = tmp_path / "snapshot.py"
    fake.write_text("SNAPSHOT_TTL_SEC = 60\nQUOTA_WARN_FRAC = telemetry_config()['x']\n",
                    encoding="utf-8")
    monkeypatch.setattr(m, "_SNAPSHOT", fake)
    monkeypatch.setattr(m, "_CONFIG_SOURCED", ["SNAPSHOT_TTL_SEC", "QUOTA_WARN_FRAC"])
    v = m._check_config_sourced()
    assert any("SNAPSHOT_TTL_SEC is hardcoded" in x for x in v)
    assert not any("QUOTA_WARN_FRAC" in x for x in v)  # the config-sourced one passes


def test_telemetry_schema_flags_missing_and_type(monkeypatch, tmp_path):
    m = _mod()
    bad = tmp_path / "telemetry-config.json"
    bad.write_text('{"ttl": {"snapshot_sec": "x"}, "probe": {"deadline_sec": 12}}',
                   encoding="utf-8")
    monkeypatch.setattr(m, "_TELEMETRY_JSON", bad)
    v = m._check_telemetry_schema()
    assert any("wrong type" in x for x in v)               # snapshot_sec: str
    assert any("missing section 'display'" in x for x in v)  # whole section absent


def test_routing_knobs_flag_missing(monkeypatch, tmp_path):
    m = _mod()
    bad = tmp_path / "routing-config.json"
    bad.write_text('{"token_load_balancing": {"enabled": true}}', encoding="utf-8")
    monkeypatch.setattr(m, "_ROUTING_JSON", bad)
    v = m._check_routing_knobs()
    assert any("context_affinity" in x for x in v)
