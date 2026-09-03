"""
saturation-scan.py — Codebase saturation and health checker.

Triggered automatically every 10 commits via commit_count in state.json.
Checks: (1) file line counts, (2) invariant sequence completeness,
        (3) stale old-layout path literals in Python files.

Usage:
  python saturation-scan.py [--sys-root PATH] [--force] [--checks lines invariants imports]
                             [--write-report]
Exit: 0 = clean (or skip), 1 = HIGH findings present.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple


# ─── Thresholds ────────────────────────────────────────────────────────────────
LINE_LIMITS: dict[str, int] = {
    ".py": 600,
    ".md": 400,
    ".json": 1000,
    ".bat": 200,
}

EXCLUDE_DIRS: frozenset[str] = frozenset({
    "env", "tools", "data", "__pycache__", ".git", "node_modules",
    "results", "tmp", "history",
    # Vendor/marketplace/cache content installed by peer CLIs under
    # {peer}/config/ (antigravity skills marketplace, codex plugin cache
    # + built-in skill system, claude plugin marketplace, peer-generated
    # scratch/cache dirs) - not this project's own source, so its line
    # counts shouldn't be graded against our conventions. ".tmp"/".system"
    # deliberately duplicate "tmp" for the dotfile-named variant actually
    # used by codex's cache dir (a plain "tmp" match doesn't catch ".tmp").
    ".tmp", ".system", "skills", "plugins", "marketplaces", "cache", "scratch",
    "brain",  # ag's own cross-session memory store, not this project's source
})

# Specific vendor-generated files that live directly under a peer's config/
# dir (not caught by EXCLUDE_DIRS since it's a single file, not a subdir) -
# e.g. Claude Code's own CLI settings/telemetry state.
EXCLUDE_FILES: frozenset[str] = frozenset({".claude.json"})

# Path literal prefixes that belong to old _sys layout (flag if still present)
OLD_LAYOUT_PREFIXES: tuple[str, ...] = (
    '"ai/', "'ai/",
    '"claude/', "'claude/",
    '"gemini/', "'gemini/",
    '"codex/', "'codex/",
)


# ─── Result types ──────────────────────────────────────────────────────────────
class Finding(NamedTuple):
    severity: str   # HIGH | MEDIUM | LOW
    category: str   # lines | invariants | imports
    path: str
    detail: str


# ─── Helpers ───────────────────────────────────────────────────────────────────
def _is_excluded(fp: Path, sys_root: Path) -> bool:
    # Check parts relative to sys_root only - an exclude name coincidentally
    # appearing in sys_root's own ancestry (e.g. this project's sandboxed
    # TEMP redirecting through a directory named "data") must not affect
    # matching, only the structure actually being scanned.
    try:
        rel_parts = fp.relative_to(sys_root).parts
    except ValueError:
        rel_parts = fp.parts
    return fp.name in EXCLUDE_FILES or any(part in EXCLUDE_DIRS for part in rel_parts)


# ─── Check 1: File line counts ─────────────────────────────────────────────────
def scan_lines(sys_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for ext, limit in LINE_LIMITS.items():
        for fp in sys_root.rglob(f"*{ext}"):
            if _is_excluded(fp, sys_root):
                continue
            try:
                line_count = fp.read_text("utf-8", errors="replace").count("\n")
            except OSError:
                continue
            if line_count > limit:
                severity = "HIGH" if line_count > limit * 1.5 else "MEDIUM"
                findings.append(Finding(
                    severity=severity,
                    category="lines",
                    path=str(fp.relative_to(sys_root)),
                    detail=f"{line_count} lines (limit {limit})",
                ))
    return findings


# ─── Check 2: Invariant sequence completeness ──────────────────────────────────
_INV_ROW = re.compile(r"\|\s*(INV-\d+)\s*\|")
_PRO_ROW = re.compile(r"\|\s*(PRO-\d+)\s*\|")


def _parse_invariant_ids(text: str) -> tuple[set[str], set[str]]:
    return set(_INV_ROW.findall(text)), set(_PRO_ROW.findall(text))


def _sequence_gaps(prefix: str, ids: set[str]) -> list[str]:
    nums = sorted(int(s.split("-")[1]) for s in ids)
    if not nums:
        return []
    full = {f"{prefix}-{i:02d}" for i in range(nums[0], nums[-1] + 1)}
    return sorted(full - ids)


def _find_invariants_file(sys_root: Path) -> Path | None:
    candidates = [
        sys_root / "docs" / "history" / "engram-peer-governance" / "10-invariants.md",
        sys_root.parent / "_sys" / "docs" / "history" / "engram-peer-governance" / "10-invariants.md",
    ]
    return next((c for c in candidates if c.exists()), None)


def scan_invariants(sys_root: Path) -> list[Finding]:
    findings: list[Finding] = []

    inv_path = _find_invariants_file(sys_root)
    if inv_path is None:
        # Post-separation: INV/PRO multi-peer governance is retired and archived.
        # Gracefully skip if invariants file is not present.
        return findings

    text = inv_path.read_text("utf-8")
    invs, pros = _parse_invariant_ids(text)
    rel = str(inv_path.relative_to(sys_root) if inv_path.is_relative_to(sys_root) else inv_path)

    for prefix, ids in (("INV", invs), ("PRO", pros)):
        gaps = _sequence_gaps(prefix, ids)
        if gaps:
            findings.append(Finding(
                "MEDIUM", "invariants", rel,
                f"{prefix} sequence gaps: {gaps}",
            ))

    # Cross-check governance_params.json for references to unknown invariants
    gov_candidates = [
        sys_root / "config" / "protocol" / "governance.json",
        sys_root.parent / "_sys" / "ai" / "governance_params.json",
    ]
    gov_path = next((c for c in gov_candidates if c.exists()), None)
    if gov_path:
        try:
            gov_text = gov_path.read_text("utf-8")
            referenced = set(re.findall(r"(?:INV|PRO)-\d+", gov_text))
            unknown = referenced - invs - pros
            if unknown:
                findings.append(Finding(
                    "LOW", "invariants", gov_path.name,
                    f"References unknown invariant IDs: {sorted(unknown)}",
                ))
        except OSError:
            pass

    return findings


# ─── Check 3: Stale old-layout path literals in Python files ──────────────────
_PATH_LITERAL = re.compile(
    r'(?:Path\(["\'])([^"\']+)["\']'
    r'|["\']([^"\']*(?:\.json|\.jsonl|\.md))["\']'
)

_OLD_PREFIXES = (
    "ai/", "claude/", "gemini/", "codex/", "antigravity/",
)


def _stale_literals_in_file(fp: Path, sys_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        src = fp.read_text("utf-8", errors="replace")
        ast.parse(src, filename=str(fp))  # syntax check
    except SyntaxError as e:
        return [Finding("HIGH", "imports", str(fp.relative_to(sys_root)), f"SyntaxError: {e}")]
    except OSError:
        return []

    for m in _PATH_LITERAL.finditer(src):
        raw = m.group(1) or m.group(2) or ""
        if not raw:
            continue
        if any(raw.startswith(pfx) for pfx in _OLD_PREFIXES):
            new_path = sys_root / raw
            if not new_path.exists():
                findings.append(Finding(
                    "MEDIUM", "imports",
                    str(fp.relative_to(sys_root)),
                    f"Stale old-layout path literal: {raw!r}",
                ))
    return findings


def scan_imports(sys_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for fp in sys_root.rglob("*.py"):
        if _is_excluded(fp, sys_root):
            continue
        findings.extend(_stale_literals_in_file(fp, sys_root))
    return findings


# ─── State: commit_count trigger ──────────────────────────────────────────────
def _read_commit_count(sys_root: Path) -> int | None:
    """Return the tracked commit_count, or None if no state file declares one.

    A missing key must not be conflated with a legitimate commit_count=0: no
    writer currently populates this key (grep confirms no producer exists),
    so ``.get("commit_count", 0)`` previously made every run look like an
    exact multiple of 10 and fired unconditionally (T89).
    """
    for candidate in [
        sys_root / "data" / "state" / "state.json",
        sys_root.parent / ".ai" / "state.json",
    ]:
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if "commit_count" in data:
                return data["commit_count"]
    return None


# ─── Report ───────────────────────────────────────────────────────────────────
def _print_report(findings: list[Finding]) -> None:
    by_sev: dict[str, list[Finding]] = {"HIGH": [], "MEDIUM": [], "LOW": []}
    for f in findings:
        by_sev[f.severity].append(f)

    print(f"\n=== saturation-scan: {len(findings)} finding(s) ===")
    for sev in ("HIGH", "MEDIUM", "LOW"):
        group = by_sev[sev]
        if group:
            print(f"\n[{sev}] {len(group)} item(s)")
            for f in group:
                print(f"  [{f.category}] {f.path}")
                print(f"    → {f.detail}")

    if not findings:
        print("  All checks passed.")


def _write_report(findings: list[Finding], sys_root: Path) -> None:
    report_dir = sys_root / "data" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out = report_dir / f"saturation-{ts}.json"
    out.write_text(
        json.dumps([f._asdict() for f in findings], indent=2, ensure_ascii=False),
        "utf-8",
    )
    print(f"[REPORT] {out}")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser(description="Saturation scan for _sys")
    p.add_argument("--sys-root", default=str(Path(__file__).resolve().parent.parent),
                   help="Path to _sys root")
    p.add_argument("--force", action="store_true",
                   help="Run even when commit_count %% 10 != 0")
    p.add_argument("--checks", nargs="+",
                   choices=["lines", "invariants", "imports"],
                   default=["lines", "invariants", "imports"],
                   metavar="CHECK")
    p.add_argument("--write-report", action="store_true",
                   help="Save JSON report to data/reports/")
    args = p.parse_args()

    sys_root = Path(args.sys_root)
    commit_count = _read_commit_count(sys_root)

    if not args.force:
        if commit_count is None:
            print("[SKIP] commit_count not tracked in state.json — use --force to run now.")
            sys.exit(0)
        # commit_count=0 is grouped with "missing" (T89 criterion c): nothing
        # writes this key yet, so an explicit 0 is as untrustworthy a trigger
        # as a missing key, and 0 % 10 == 0 would otherwise fire every time.
        if commit_count == 0 or commit_count % 10 != 0:
            print(f"[SKIP] commit_count={commit_count} — not a multiple of 10. Use --force to run now.")
            sys.exit(0)

    count_display = commit_count if commit_count is not None else "untracked"
    print(f"[START] saturation-scan  sys_root={sys_root}  commit_count={count_display}")
    findings: list[Finding] = []

    check_map = {
        "lines": scan_lines,
        "invariants": scan_invariants,
        "imports": scan_imports,
    }
    for name in args.checks:
        result = check_map[name](sys_root)
        print(f"  {name}: {len(result)} finding(s)")
        findings.extend(result)

    _print_report(findings)

    if args.write_report:
        _write_report(findings, sys_root)

    sys.exit(1 if any(f.severity == "HIGH" for f in findings) else 0)


if __name__ == "__main__":
    main()
