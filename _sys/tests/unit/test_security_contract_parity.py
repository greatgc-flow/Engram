"""B7 — declarative security_contract parity (_check_flag_parity).

The security expectations (required/forbidden flags, sandbox semantics) now live
in orchestration.json per-peer `security_contract`, not hardcoded in hub.py. The
parity check reads them, skips disabled/contract-less peers, and reconciles the
hub adapter command against the peer_console defaults.
"""
import copy
import json
import sys
from pathlib import Path

SYS_CORE = Path(__file__).resolve().parents[2] / "core"
if str(SYS_CORE) not in sys.path:
    sys.path.insert(0, str(SYS_CORE))

import hub  # noqa: E402

_ORCH = Path(__file__).resolve().parents[2] / "ai" / "orchestration.json"


def _real_orch():
    return json.loads(_ORCH.read_text(encoding="utf-8-sig"))


def _peer(orch, node_id):
    return next(n for n in orch["hub_nodes"] if n.get("node_id") == node_id)


def test_real_config_parity_is_clean():
    # The shipped contracts must match the shipped invoke_args on both paths.
    assert hub._check_flag_parity() == []


def test_required_flag_violation_is_detected(monkeypatch):
    orch = copy.deepcopy(_real_orch())
    _peer(orch, "cc")["security_contract"]["required_effective_args"].append("--flag-that-is-not-there")
    monkeypatch.setattr(hub, "_load_orchestration", lambda: orch)
    errs = hub._check_flag_parity()
    assert any("--flag-that-is-not-there" in e and "cc" in e for e in errs)


def test_forbidden_flag_violation_is_detected(monkeypatch):
    orch = copy.deepcopy(_real_orch())
    # cc's invoke_args legitimately contain --dangerously-skip-permissions; mark a
    # substring of it forbidden to force a hit deterministically.
    _peer(orch, "cc")["security_contract"]["forbidden_effective_args"].append("skip-permissions")
    monkeypatch.setattr(hub, "_load_orchestration", lambda: orch)
    errs = hub._check_flag_parity()
    assert any("forbidden" in e and "skip-permissions" in e for e in errs)


def test_disabled_peer_is_skipped(monkeypatch):
    orch = copy.deepcopy(_real_orch())
    # Give the DISABLED ca alias an impossible contract; it must NOT false-fail.
    ca = _peer(orch, "ca")
    assert ca.get("enabled") is False
    ca["security_contract"] = {"required_effective_args": ["--impossible"],
                               "forbidden_effective_args": [], "sandbox_semantics": None}
    monkeypatch.setattr(hub, "_load_orchestration", lambda: orch)
    errs = hub._check_flag_parity()
    assert not any("ca" in e for e in errs)


def test_absent_contract_is_skipped(monkeypatch):
    orch = copy.deepcopy(_real_orch())
    _peer(orch, "cc").pop("security_contract", None)
    monkeypatch.setattr(hub, "_load_orchestration", lambda: orch)
    # cc no longer contributes any parity error (nothing declared to reconcile).
    errs = hub._check_flag_parity()
    assert not any(e.startswith("PARITY cc:") for e in errs)


def test_workspace_write_semantic_missing_is_detected(monkeypatch):
    orch = copy.deepcopy(_real_orch())
    cx = _peer(orch, "cx")
    # Strip the sandbox override from invoke_args so the semantic check fails.
    cx["invoke_args"] = [a for a in cx["invoke_args"] if "workspace-write" not in str(a)]
    monkeypatch.setattr(hub, "_load_orchestration", lambda: orch)
    errs = hub._check_flag_parity()
    assert any("workspace-write sandbox missing" in e and "cx" in e for e in errs)
