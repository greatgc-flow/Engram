"""
GAP-1 Detection — API Signature Snapshot Tests (TDD Red Phase)

Captures hub.py public API signatures to a JSON snapshot.
On subsequent runs, any signature drift causes test failure.
Developer must run 'python hub.py update-signatures' to acknowledge changes,
then update test_contracts.py to match.
"""
import inspect
import json
import sys
from pathlib import Path
from typing import Any

import pytest

SYS_DIR = Path(__file__).parent.parent.parent.resolve()
SNAPSHOT_PATH = SYS_DIR / "ai" / "snapshots" / "hub_api.json"

sys.path.insert(0, str(SYS_DIR))
import core.hub as hub


# Public API patterns to snapshot
_API_PATTERNS = (
    "_lease_cfg",
)
_ACTION_PREFIX = "action_"


def _extract_param_info(sig: inspect.Signature) -> dict[str, Any]:
    params = {}
    for name, p in sig.parameters.items():
        entry: dict[str, Any] = {"kind": p.kind.name}
        if p.default is not inspect.Parameter.empty:
            try:
                json.dumps(p.default)  # only serializable defaults
                entry["default"] = p.default
            except (TypeError, ValueError):
                entry["default"] = repr(p.default)
        if p.annotation is not inspect.Parameter.empty:
            entry["annotation"] = str(p.annotation)
        params[name] = entry
    return params


def _extract_signatures() -> dict[str, Any]:
    """Extract all monitored hub.py API signatures."""
    sigs = {}
    for name in dir(hub):
        if name in _API_PATTERNS or name.startswith(_ACTION_PREFIX):
            obj = getattr(hub, name)
            if callable(obj):
                try:
                    sig = inspect.signature(obj)
                    sigs[name] = {
                        "params": _extract_param_info(sig),
                        "return": str(sig.return_annotation),
                    }
                except (ValueError, TypeError):
                    pass
    return sigs


class TestSignatureSnapshotExists:
    """Snapshot file must exist and be up-to-date."""

    def test_snapshot_file_exists(self):
        assert SNAPSHOT_PATH.exists(), (
            f"Signature snapshot missing: {SNAPSHOT_PATH}\n"
            "Run: python _sys/core/hub.py update-signatures"
        )

    def test_snapshot_is_valid_json(self):
        if not SNAPSHOT_PATH.exists():
            pytest.skip("snapshot file missing")
        data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, dict), "Snapshot must be a JSON object"
        assert "signatures" in data, "Snapshot must have 'signatures' key"
        assert "generated_at" in data, "Snapshot must have 'generated_at' key"

    def test_snapshot_covers_core_apis(self):
        if not SNAPSHOT_PATH.exists():
            pytest.skip("snapshot file missing")
        sigs = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))["signatures"]
        for name in _API_PATTERNS:
            assert name in sigs, f"Snapshot missing core API: {name}"

    def test_snapshot_covers_action_functions(self):
        if not SNAPSHOT_PATH.exists():
            pytest.skip("snapshot file missing")
        sigs = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))["signatures"]
        action_names = [k for k in sigs if k.startswith(_ACTION_PREFIX)]
        assert len(action_names) >= 20, (
            f"Snapshot only covers {len(action_names)} action_* functions, expected >= 20"
        )


class TestSignatureDrift:
    """Current signatures must match snapshot exactly."""

    @pytest.fixture(scope="class")
    def snapshot(self):
        if not SNAPSHOT_PATH.exists():
            pytest.skip("snapshot file missing — run hub.py update-signatures")
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))["signatures"]

    @pytest.fixture(scope="class")
    def current(self):
        return _extract_signatures()

    def test_no_missing_apis(self, snapshot, current):
        """APIs in snapshot must still exist in hub.py."""
        missing = set(snapshot) - set(current)
        assert not missing, (
            f"APIs removed from hub.py without updating snapshot:\n{missing}\n"
            "Run: python _sys/core/hub.py update-signatures"
        )

    def test_no_added_apis_without_snapshot_update(self, snapshot, current):
        """New public APIs must be added to snapshot (run update-signatures)."""
        added = set(current) - set(snapshot)
        assert not added, (
            f"New APIs in hub.py not in snapshot:\n{added}\n"
            "Run: python _sys/core/hub.py update-signatures"
        )

    def test_no_param_drift(self, snapshot, current):
        """Parameter signatures must match snapshot exactly."""
        drifted = []
        for name in set(snapshot) & set(current):
            snap_params = snapshot[name]["params"]
            curr_params = current[name]["params"]
            if snap_params != curr_params:
                drifted.append(
                    f"{name}: snapshot={list(snap_params)} current={list(curr_params)}"
                )
        assert not drifted, (
            "Parameter drift detected — update test_contracts.py then run:\n"
            "python _sys/core/hub.py update-signatures\n\n"
            + "\n".join(drifted)
        )

    def test_no_return_type_drift(self, snapshot, current):
        """Return type annotations must match snapshot."""
        drifted = []
        for name in set(snapshot) & set(current):
            snap_ret = snapshot[name]["return"]
            curr_ret = current[name]["return"]
            if snap_ret != curr_ret:
                drifted.append(f"{name}: snapshot={snap_ret!r} current={curr_ret!r}")
        assert not drifted, (
            "Return type drift detected — update test_contracts.py then run:\n"
            "python _sys/core/hub.py update-signatures\n\n"
            + "\n".join(drifted)
        )

    def test_no_default_value_drift(self, snapshot, current):
        """Default values for optional params must match snapshot."""
        drifted = []
        for name in set(snapshot) & set(current):
            for param, snap_info in snapshot[name]["params"].items():
                curr_info = current[name]["params"].get(param, {})
                snap_default = snap_info.get("default", "<<missing>>")
                curr_default = curr_info.get("default", "<<missing>>")
                if snap_default != curr_default:
                    drifted.append(
                        f"{name}.{param}: snapshot_default={snap_default!r} "
                        f"current_default={curr_default!r}"
                    )
        assert not drifted, (
            "Default value drift — a changed default is a breaking change:\n"
            + "\n".join(drifted)
        )


class TestUpdateSignaturesCommand:
    """hub.py update-signatures command must exist and generate valid output."""

    def test_update_signatures_subcommand_registered(self):
        """hub.py CLI must have 'update-signatures' subcommand."""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(SYS_DIR / "core" / "hub.py"), "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert "update-signatures" in result.stdout or "update-signatures" in result.stderr, (
            "hub.py must have 'update-signatures' subcommand.\n"
            "Add it to generate/update _sys/ai/snapshots/hub_api.json"
        )
