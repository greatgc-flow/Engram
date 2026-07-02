#!/usr/bin/env python3
"""check_cli_reality.py — empirical declared-vs-actual reconciliation for peer CLIs.

Closes Topic F (the declared-vs-actual gap): reconciles orchestration.json
declarations against what the REAL peer binaries actually are/do. Runs the real
binaries only (never the `_sys/cli/*.bat` wrappers, which shadow bare names on
PATH and run a heavy hub entry flow). `--help` is a hypothesis generator, never
evidence. Anything not measured renders literally as `absent` — never estimated
or fabricated (this is the check that would have caught the nonexistent
"GPT-4o (3P)" and the asserted-but-unverified `verified_local`).

Emits a drift report OVERLAY; it NEVER mutates orchestration.json (declaration
changes must go through consensus). Machine-owned verdicts only.

Verdicts:
  MATCH         declared == observed
  DRIFT         declared != observed, both measured
  ABSENT        observed could not be measured  (renders literal "absent")
  CONTRADICTED  declared thing does not exist in the actual set
                (e.g. a model id that is not in the CLI's real model list)
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SYS_DIR = Path(__file__).resolve().parent.parent  # _sys/
_PORTABLE_ROOT = SYS_DIR.parent
_AI_DIR = _PORTABLE_ROOT / ".ai"

# The ONLY trusted invocation targets. Never the _sys/cli/*.bat wrappers.
REAL_BINARIES: dict[str, Path] = {
    "cc": SYS_DIR / "env" / "nodejs" / "npm-global" / "claude.cmd",
    "cx": SYS_DIR / "env" / "nodejs" / "npm-global" / "codex.cmd",
    "ag": SYS_DIR / "tools" / "agy" / "agy.exe",
}
_WRAPPER_DIR = (SYS_DIR / "cli").resolve()

VERDICT_MATCH = "MATCH"
VERDICT_DRIFT = "DRIFT"
VERDICT_ABSENT = "ABSENT"
VERDICT_CONTRADICTED = "CONTRADICTED"


# ── pure logic (unit-tested; no live CLI) ────────────────────────────────────

def real_binary(peer: str) -> Path:
    """Resolve a peer to its real binary path. Raises on unknown peer."""
    try:
        return REAL_BINARIES[peer]
    except KeyError as exc:
        raise KeyError(f"unknown peer {peer!r}") from exc


def is_wrapper(path: str | Path) -> bool:
    """True if path lives in _sys/cli (a hub wrapper), which must never be probed."""
    try:
        return Path(path).resolve().parent == _WRAPPER_DIR
    except OSError:
        return False


def classify_model(declared: str, actual_list: list[str] | None) -> str:
    """A declared model id against the CLI's real model list."""
    if actual_list is None:
        return VERDICT_ABSENT
    return VERDICT_MATCH if declared in actual_list else VERDICT_CONTRADICTED


def classify_scalar(declared: Any, observed: Any) -> str:
    """A declared scalar (e.g. version) against a measured one."""
    if observed is None:
        return VERDICT_ABSENT
    if declared is None:
        return VERDICT_DRIFT  # measured something not declared
    return VERDICT_MATCH if str(declared) == str(observed) else VERDICT_DRIFT


def fingerprint(path: str | Path) -> dict[str, Any]:
    """Content+metadata fingerprint of a binary; sha256 drift = CLI updated."""
    p = Path(path)
    if not p.exists():
        return {"path": str(p), "exists": False, "sha256": None, "size": None, "mtime": None}
    data = p.read_bytes()
    return {
        "path": str(p),
        "exists": True,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "mtime": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
    }


def fingerprint_changed(current: dict, baseline: dict | None) -> bool:
    """True when the binary content changed (or there is no baseline yet)."""
    if not baseline:
        return True
    return current.get("sha256") != baseline.get("sha256")


def _severity(verdict: str) -> str:
    return {
        VERDICT_CONTRADICTED: "P0",
        VERDICT_DRIFT: "P1",
        VERDICT_ABSENT: "P2",
        VERDICT_MATCH: "ok",
    }[verdict]


def reconcile_peer(
    peer: str,
    declared_models: list[str],
    observed: dict[str, Any],
) -> dict[str, Any]:
    """Reconcile one peer's declarations against measured `observed`:
    observed = {"version": str|None, "actual_models": list|None, "fingerprint": dict}.
    Returns a peer report block with per-probe verdicts. Never estimates.
    """
    actual_models = observed.get("actual_models")
    model_probes = [
        {
            "kind": "model",
            "declared": m,
            "observed": (m if (actual_models and m in actual_models) else None),
            "verdict": classify_model(m, actual_models),
        }
        for m in declared_models
    ]
    version_verdict = classify_scalar(observed.get("declared_version"), observed.get("version"))
    probes = [
        {
            "kind": "version",
            "declared": observed.get("declared_version"),
            "observed": observed.get("version"),
            "verdict": version_verdict,
        },
        *model_probes,
    ]
    for p in probes:
        p["severity"] = _severity(p["verdict"])
    return {
        "peer": peer,
        "binary": str(real_binary(peer)),
        "fingerprint": observed.get("fingerprint"),
        "probes": probes,
        "drift": [p for p in probes if p["verdict"] in (VERDICT_DRIFT, VERDICT_CONTRADICTED)],
    }


def build_report(peer_reports: list[dict], observed_at: str | None = None) -> dict[str, Any]:
    """Assemble the drift report overlay. Pure aggregation; no I/O, no mutation."""
    all_drift = [
        {"peer": pr["peer"], **d} for pr in peer_reports for d in pr["drift"]
    ]
    return {
        "schema_version": 1,
        "kind": "cli_reality_drift_report",
        "observed_at": observed_at or datetime.now().isoformat(timespec="seconds"),
        "peers": peer_reports,
        "drift_summary": {
            "total": len(all_drift),
            "p0": sum(1 for d in all_drift if d["severity"] == "P0"),
            "p1": sum(1 for d in all_drift if d["severity"] == "P1"),
            "items": all_drift,
        },
        "note": "Overlay only. Never mutates orchestration.json; declaration changes require consensus.",
    }


# ── live probes (impure; safe, bounded, honest-absent on any failure) ─────────

def probe_version(peer: str, timeout: int = 20) -> str | None:
    """Run the REAL binary `--version`; return first semver-ish token or None."""
    binary = real_binary(peer)
    if is_wrapper(binary) or not binary.exists():
        return None
    try:
        out = subprocess.run(
            [str(binary), "--version"],
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"\d+\.\d+\.\d+", f"{out.stdout or ''}{out.stderr or ''}")
    return m.group(0) if m else None


def load_observed_models(peer: str) -> list[str] | None:
    """Load a provenance-tagged verified capture of a peer's real model list from
    `.ai/cli-reality-observed.json` if present, else None (=> ABSENT). We do NOT
    guess a model list — some CLIs (agy) require a PTY to enumerate, so the list
    is populated out-of-band by a verified capture and only trusted from that file.
    """
    path = _AI_DIR / "cli-reality-observed.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entry = data.get(peer)
    if isinstance(entry, dict):
        models = entry.get("models")
        return models if isinstance(models, list) else None
    return None


def _declared(orch: dict, peer: str) -> tuple[list[str], str | None]:
    node = next((n for n in orch.get("hub_nodes", []) if n.get("node_id") == peer), None)
    if not node:
        return [], None
    models: list[str] = []
    for prof in (node.get("profiles") or {}).values():
        mid = prof.get("model_id") or prof.get("runtime_model")
        if mid:
            models.append(mid)
    return models, None  # declared_version unknown until a versions map is declared


def run(orch: dict | None = None, live: bool = True) -> dict[str, Any]:
    """Reconcile every real-binary peer. `live=False` skips subprocess calls
    (fingerprint + reconciliation against the observed-capture file only)."""
    if orch is None:
        orch_path = SYS_DIR / "ai" / "orchestration.json"
        orch = json.loads(orch_path.read_text(encoding="utf-8"))
    reports = []
    for peer in REAL_BINARIES:
        declared_models, declared_version = _declared(orch, peer)
        observed = {
            "fingerprint": fingerprint(real_binary(peer)),
            "declared_version": declared_version,
            "version": probe_version(peer) if live else None,
            "actual_models": load_observed_models(peer),
        }
        reports.append(reconcile_peer(peer, declared_models, observed))
    return build_report(reports)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    live = "--no-live" not in argv
    report = run(live=live)
    if "--json" in argv:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        s = report["drift_summary"]
        print(f"[cli-reality] drift: {s['total']} (P0={s['p0']} P1={s['p1']}) checked_at={report['observed_at']}")
        for d in s["items"]:
            print(f"  {d['severity']:>2} {d['peer']}.{d['kind']}: {d['verdict']} declared={d['declared']!r} observed={d['observed']!r}")
        if not s["items"]:
            print("  (no drift; note: unmeasured fields render ABSENT, not MATCH)")
    # P0 drift (a declared thing that does not exist) exits non-zero for CI.
    return 2 if report["drift_summary"]["p0"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
