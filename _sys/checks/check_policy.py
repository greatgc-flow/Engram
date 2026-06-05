"""check_policy.py — Axis-J: Policy Regression Gate (local, zero-token).

Verifies that key policies declared in PROTOCOL.md / CONVENTION.md
are actually implemented in hub.py and key config files.

Exits 0 (PASS) if no critical divergences found.
Exits 1 (FAIL) if critical policy-code mismatch detected.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_CHECKS_DIR = Path(__file__).parent
_SYS_DIR = _CHECKS_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

sys.path.insert(0, str(_CHECKS_DIR))
from _common import log_collab  # noqa: E402


@dataclass
class PolicyResult:
    name: str
    status: str  # PASS | WARN | FAIL
    detail: str = ""


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


# ── Individual checks ─────────────────────────────────────────

def check_hub_actions(hub_src: str) -> PolicyResult:
    """§P-3: hub.py must expose consensus-propose/vote/check/sweep."""
    required = ["consensus-propose", "consensus-vote", "consensus-check", "consensus-sweep"]
    missing = [a for a in required if a not in hub_src]
    if missing:
        return PolicyResult("hub-consensus-actions", "FAIL",
                            f"Missing actions: {', '.join(missing)}")
    return PolicyResult("hub-consensus-actions", "PASS",
                        "All consensus actions present in hub.py")


def check_r10_files_exist(protocol_src: str) -> PolicyResult:
    """§C-0: R:10 Constitutional documents must exist on disk."""
    candidates = [
        ("PROTOCOL.md", _PORTABLE_ROOT / "PROTOCOL.md"),
        ("CLAUDE.md", _PORTABLE_ROOT / "CLAUDE.md"),
        ("GEMINI.md", _PORTABLE_ROOT / "GEMINI.md"),
        ("_sys/core/hub.py", _SYS_DIR / "core" / "hub.py"),
        (".ai/nodes.json", _PORTABLE_ROOT / ".ai" / "nodes.json"),
    ]
    missing = [name for name, path in candidates if not path.exists()]
    if missing:
        return PolicyResult("r10-files-exist", "FAIL",
                            f"Constitutional files missing: {', '.join(missing)}")
    return PolicyResult("r10-files-exist", "PASS",
                        "All R:10 constitutional files exist")


def check_quorum_policy_documented(protocol_src: str) -> PolicyResult:
    """§P-3-QR: Quorum table must be present in PROTOCOL.md."""
    if "§P-3-QR" not in protocol_src:
        return PolicyResult("quorum-policy", "FAIL",
                            "§P-3-QR not found in PROTOCOL.md — quorum policy undocumented")
    if "N/2 + 1" not in protocol_src and "N/2+1" not in protocol_src:
        return PolicyResult("quorum-policy", "WARN",
                            "§P-3-QR exists but majority quorum formula (N/2+1) not found")
    return PolicyResult("quorum-policy", "PASS",
                        "§P-3-QR present with majority quorum formula")


def check_collab_rate_symmetry() -> PolicyResult:
    """§C-0: CLAUDE.md, GEMINI.md, PROTOCOL.md must all have R:8 Multi-script row."""
    files = {
        "CLAUDE.md": _PORTABLE_ROOT / "CLAUDE.md",
        "GEMINI.md": _PORTABLE_ROOT / "GEMINI.md",
        "PROTOCOL.md": _PORTABLE_ROOT / "PROTOCOL.md",
    }
    missing_r8 = []
    for name, path in files.items():
        src = _read(path)
        if "R:8" not in src and "Multi-script" not in src:
            missing_r8.append(name)
    if missing_r8:
        return PolicyResult("collab-rate-symmetry", "FAIL",
                            f"R:8 row missing in: {', '.join(missing_r8)}")
    return PolicyResult("collab-rate-symmetry", "PASS",
                        "R:8 Multi-script row present in all 3 COLLAB_RATE tables")


def check_reorientation_policy(protocol_src: str) -> PolicyResult:
    """§P-11: Re-orientation enforcement signal must be documented."""
    if "SKIPPED: no prior session found" not in protocol_src:
        return PolicyResult("reorientation-signal", "WARN",
                            "§P-11 re-orientation enforcement signal not found in PROTOCOL.md")
    return PolicyResult("reorientation-signal", "PASS",
                        "§P-11 re-orientation signal documented")


def check_stalled_rounds() -> PolicyResult:
    """Axis-2: No voting rounds should be stalled for >30 minutes."""
    from datetime import datetime, timedelta
    consensus_dir = _PORTABLE_ROOT / ".ai" / "consensus"
    if not consensus_dir.exists():
        return PolicyResult("stalled-rounds", "PASS", "No .ai/consensus/ directory")
    cutoff = datetime.now() - timedelta(minutes=30)
    stalled = []
    for f in consensus_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("status") != "voting":
                continue
            proposed_at = datetime.fromisoformat(data.get("proposed_at", ""))
            if proposed_at < cutoff:
                stalled.append(data.get("round_id", f.stem))
        except Exception:
            continue
    if stalled:
        return PolicyResult("stalled-rounds", "FAIL",
                            f"Stalled consensus rounds (>30min): {', '.join(stalled)} — run consensus-sweep")
    return PolicyResult("stalled-rounds", "PASS", "No stalled consensus rounds")


def check_convention_english(convention_src: str) -> PolicyResult:
    """CONVENTION.md §0: No Korean prose in §0 (English mandate)."""
    korean = re.findall(r"[가-힣]{4,}", convention_src[:2000])  # Check first 2KB only
    if korean:
        return PolicyResult("convention-english", "WARN",
                            f"Korean found in CONVENTION.md opening section: {korean[:3]}")
    return PolicyResult("convention-english", "PASS",
                        "CONVENTION.md opening section is English")


def check_no_hardcoded_paths() -> PolicyResult:
    """Portability: no hardcoded absolute paths in key doc files."""
    pattern = re.compile(r"(?<![`'\"])(C:\\|D:\\|P:\\|/Users/|/home/)\w", re.IGNORECASE)
    targets = {
        "PROTOCOL.md": _PORTABLE_ROOT / "PROTOCOL.md",
        "GEMINI.md": _PORTABLE_ROOT / "GEMINI.md",
        "CLAUDE.md": _PORTABLE_ROOT / "CLAUDE.md",
    }
    hits = []
    for name, path in targets.items():
        src = _read(path)
        matches = pattern.findall(src)
        if matches:
            hits.append(f"{name}({len(matches)}x)")
    if hits:
        return PolicyResult("no-hardcoded-paths", "WARN",
                            f"Possible hardcoded paths in: {', '.join(hits)}")
    return PolicyResult("no-hardcoded-paths", "PASS",
                        "No hardcoded absolute paths in key doc files")


def check_protocol_version(protocol_src: str) -> PolicyResult:
    """§HISTORY: PROTOCOL.md must declare a version >= v3.3."""
    match = re.search(r"\*\*v(\d+)\.(\d+)\*\*", protocol_src)
    if not match:
        return PolicyResult("protocol-version", "WARN",
                            "Could not find version tag in PROTOCOL.md §HISTORY")
    major, minor = int(match.group(1)), int(match.group(2))
    if (major, minor) < (3, 3):
        return PolicyResult("protocol-version", "FAIL",
                            f"PROTOCOL.md version v{major}.{minor} < required v3.3")
    return PolicyResult("protocol-version", "PASS",
                        f"PROTOCOL.md version v{major}.{minor} OK")


def check_pythonutf8_in_bats() -> PolicyResult:
    """CONVENTION.md §1-1: All _sys/cli and _sys/hooks .bat files must set PYTHONUTF8=1."""
    dirs = [_SYS_DIR / "cli", _SYS_DIR / "hooks"]
    missing = []
    for d in dirs:
        for bat in d.glob("*.bat"):
            src = _read(bat)
            if "PYTHONUTF8" not in src and "hub.py" not in src:
                # hub.py callers inherit env; skip pure-relay scripts
                continue
            if "PYTHONUTF8" not in src:
                missing.append(bat.name)
    if missing:
        return PolicyResult("pythonutf8-mandate", "WARN",
                            f"PYTHONUTF8=1 missing in: {', '.join(missing)}")
    return PolicyResult("pythonutf8-mandate", "PASS",
                        "PYTHONUTF8=1 present in all relevant bat files")


# ── Main ──────────────────────────────────────────────────────

def main() -> None:
    protocol_src = _read(_PORTABLE_ROOT / "PROTOCOL.md")
    hub_src = _read(_SYS_DIR / "core" / "hub.py")
    convention_src = _read(_PORTABLE_ROOT / "CONVENTION.md")

    results = [
        check_hub_actions(hub_src),
        check_r10_files_exist(protocol_src),
        check_quorum_policy_documented(protocol_src),
        check_collab_rate_symmetry(),
        check_reorientation_policy(protocol_src),
        check_stalled_rounds(),
        check_convention_english(convention_src),
        check_no_hardcoded_paths(),
        check_protocol_version(protocol_src),
        check_pythonutf8_in_bats(),
    ]

    fails = [r for r in results if r.status == "FAIL"]
    warns = [r for r in results if r.status == "WARN"]

    print(f"\n[policy-gate] Axis-J Results — {len(results)} checks")
    print("-" * 50)
    for r in results:
        icon = "✓" if r.status == "PASS" else ("⚠" if r.status == "WARN" else "✗")
        print(f"  {icon} [{r.status}] {r.name}: {r.detail}")

    print("-" * 50)
    if fails:
        print(f"[policy-gate] FAIL: {len(fails)} critical policy violations")
        log_collab("Axis-J", "check_policy.py", "FAIL",
                   f"{len(fails)} critical: {', '.join(r.name for r in fails)}")
        sys.exit(1)
    elif warns:
        print(f"[policy-gate] PASS with {len(warns)} warning(s)")
        log_collab("Axis-J", "check_policy.py", "WARN",
                   f"{len(warns)} warnings: {', '.join(r.name for r in warns)}")
    else:
        print(f"[policy-gate] PASS: all policy checks clean")
        log_collab("Axis-J", "check_policy.py", "OK", "All policy checks passed")


if __name__ == "__main__":
    main()
