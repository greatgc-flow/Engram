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
VERDICT_OBSERVED_ONLY = "OBSERVED_ONLY"  # measured but nothing declared => no contract to drift from


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
        # Measured a value, but nothing was declared: there is no contract to
        # drift FROM, so this is informational, not a drift (DIR-004). CLIs also
        # auto-update, so declaring a version would churn to DRIFT on every bump.
        return VERDICT_OBSERVED_ONLY
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
        VERDICT_OBSERVED_ONLY: "info",
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
    guess a model list — no CLI enumerates its models non-interactively. The file
    is produced empirically by `check_cli_canary --emit-observed` (the canary
    confirms each declared model by real invocation) and is only ever trusted from
    that file at read time.
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


def auto_refresh_observed(
    orch: dict | None = None,
    ai_root: Path | None = None,
    interval_hours: float = 24.0,
    now_ts: float | None = None
) -> dict[str, str]:
    """Auto-refresh cli-reality-observed.json if interval expired or hash changed.
    Uses SHA256 of the real CLI binary as the cache key to skip expensive real-invocation probes.
    Reuses check_cli_canary budget mechanism.
    """
    from datetime import timezone
    if orch is None:
        orch_path = SYS_DIR / "ai" / "orchestration.json"
        try:
            orch = json.loads(orch_path.read_text(encoding="utf-8"))
        except Exception:
            orch = {}
    if ai_root is None:
        ai_root = _AI_DIR
    if now_ts is None:
        now_ts = datetime.now(timezone.utc).timestamp()
    
    import check_cli_canary
    
    observed_path = ai_root / "cli-reality-observed.json"
    observed_data = {}
    if observed_path.exists():
        try:
            observed_data = json.loads(observed_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    cap, window_hours = check_cli_canary.get_budget_config(orch)
    results = {}
    needs_save = False

    for peer in REAL_BINARIES:
        fp_info = fingerprint(real_binary(peer))
        current_fp = fp_info.get("sha256")
        
        peer_data = observed_data.get(peer)
        if peer_data and isinstance(peer_data, dict):
            baseline_fp = peer_data.get("fingerprint")
            captured_at_str = peer_data.get("captured_at")
            try:
                dt = datetime.fromisoformat(captured_at_str)
                captured_at = dt.timestamp()
            except Exception:
                captured_at = 0
            
            hash_changed = (current_fp != baseline_fp)
            interval_expired = (now_ts - captured_at) >= (interval_hours * 3600)
            
            if not hash_changed:
                if not interval_expired:
                    results[peer] = "interval not yet expired"
                else:
                    results[peer] = "skipped, unchanged"
                    peer_data["captured_at"] = datetime.fromtimestamp(now_ts, timezone.utc).isoformat()
                    needs_save = True
                continue
        
        # Hash changed or no previous data -> proceed to probe
        if not check_cli_canary.check_and_update_budget(ai_root, now_ts, cap, window_hours):
            results[peer] = "skipped, budget exhausted"
            continue
            
        # Probe
        now_dt = datetime.fromtimestamp(now_ts, timezone.utc)
        verdicts = check_cli_canary.run_canary(
            orch=orch,
            peers=[peer],
            all_profiles=True,
            force=True,
            ai_root=ai_root
        )
        
        capture = check_cli_canary.build_observed_capture(verdicts, now=now_dt)
        if peer in capture:
            peer_data = capture[peer]
            peer_data["fingerprint"] = current_fp
            observed_data[peer] = peer_data
            results[peer] = "refreshed"
            needs_save = True
        else:
            results[peer] = "probe failed"

    if needs_save:
        try:
            ai_root.mkdir(parents=True, exist_ok=True)
            observed_path.write_text(json.dumps(observed_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    return results


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    
    if "--auto-refresh" in argv:
        refresh_results = auto_refresh_observed()
        print(f"[cli-reality] auto-refresh: {json.dumps(refresh_results, ensure_ascii=False)}")
        
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
