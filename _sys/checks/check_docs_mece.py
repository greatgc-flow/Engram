"""check_docs_mece.py — MECE validation for docs-v2/ (EDGE-04).

Implements 7 checks (CHK-01~07) as specified in ops/impl-plan.md §5.

Usage:
    python check_docs_mece.py [--checks CHK-01,CHK-02] [--fix] [--json]

Exit codes:
    0 — all checks pass (or only T1/T2 issues, none in fail_on list)
    1 — at least one fail_on check failed (T3 violations)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CHECKS_DIR = Path(__file__).parent
_SYS_DIR = _CHECKS_DIR.parent
_AI_DIR = _SYS_DIR / "ai"
_ROOT = _SYS_DIR.parent
_DOCS_DIR = _SYS_DIR / "docs-v2"
_GOVERNANCE_PATH = _AI_DIR / "governance_params.json"
_PROTOCOL_PATH = _AI_DIR / "protocol.json"

_HANGUL_RE = re.compile(r"[가-힣]")
_PATH_REF_RE = re.compile(r"`([_a-zA-Z0-9./\-]+\.(?:md|json|py|bat|txt))`")
_ANCHOR_REF_RE = re.compile(r"\[.*?\]\(([^)]+)\)")
_SECTION_REF_RE = re.compile(r"§(\d[\d\-\.]*)")


# ── Config ─────────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _load_config() -> dict:
    gov = _load_json(_GOVERNANCE_PATH)
    return {
        "exempt_paths": gov.get("docs_mece_exempt_paths", [
            "_archive/", "_sys/docs/history/", "Garbage/",
        ]),
        "checks_enabled": gov.get("docs_mece_checks_enabled", [
            "CHK-01", "CHK-02", "CHK-03", "CHK-04",
            "CHK-05", "CHK-06", "CHK-07",
        ]),
        "fail_on": gov.get("docs_mece_fail_on", ["CHK-01", "CHK-02"]),
        "coverage_map": gov.get("docs_mece_coverage_map", "_sys/docs-v2/ops/governance.md"),
    }


def _is_exempt(path: Path, exempt_paths: list[str]) -> bool:
    rel = str(path.relative_to(_ROOT)).replace("\\", "/")
    return any(rel.startswith(e) for e in exempt_paths)


# ── Finding model ──────────────────────────────────────────────────────────────

class Finding:
    def __init__(self, check_id: str, tier: str, path: str, line: int, message: str) -> None:
        self.check_id = check_id
        self.tier = tier
        self.path = path
        self.line = line
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "tier": self.tier,
            "path": self.path,
            "line": self.line,
            "message": self.message,
        }

    def __str__(self) -> str:
        loc = f"{self.path}:{self.line}" if self.line else self.path
        return f"[{self.check_id}/{self.tier}] {loc} — {self.message}"


# ── CHK-01: Path existence ─────────────────────────────────────────────────────

def _resolve_path(ref: str, doc_dir: Path) -> bool:
    """Try multiple resolution strategies for a path reference. Return True if found."""
    # 1. Root-relative paths (start with _sys/, workspace/, _archive/, etc.)
    if ref.startswith(("_sys/", "workspace/", "_archive/", "workspace_base/")):
        return (_ROOT / ref).exists()
    # 2. Absolute-like (shouldn't happen in docs but handle gracefully)
    if ref.startswith("/"):
        return Path(ref).exists()
    # 3. Relative to document's directory
    if (doc_dir / ref).exists():
        return True
    # 4. Relative to docs-v2 root
    if (_DOCS_DIR / ref).exists():
        return True
    # 5. Relative to _sys root
    if (_SYS_DIR / ref).exists():
        return True
    # 6. Relative to _ROOT
    return (_ROOT / ref).exists()


def chk_01_path_existence(exempt_paths: list[str]) -> list[Finding]:
    """All root-relative file paths referenced in docs-v2 *.md files must exist on disk.

    Only checks paths starting with known root prefixes (_sys/, workspace/, _archive/)
    to avoid false positives from intra-doc relative links.
    """
    _ROOT_PREFIXES = ("_sys/", "workspace/", "_archive/", "workspace_base/")
    findings: list[Finding] = []
    for md_file in _DOCS_DIR.rglob("*.md"):
        if _is_exempt(md_file, exempt_paths):
            continue
        doc_dir = md_file.parent
        lines = md_file.read_text(encoding="utf-8", errors="replace").splitlines()
        in_fence = False
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
            if in_fence:
                continue
            for match in _PATH_REF_RE.finditer(line):
                ref = match.group(1)
                if not any(ref.startswith(p) for p in _ROOT_PREFIXES):
                    continue
                if not _resolve_path(ref, doc_dir):
                    findings.append(Finding(
                        "CHK-01", "T3",
                        str(md_file.relative_to(_ROOT)).replace("\\", "/"),
                        lineno,
                        f"Referenced path not found: {ref}",
                    ))
    return findings


# ── CHK-02: INV-19 Korean detection ───────────────────────────────────────────

_INV19_KOREAN_ALLOWED_DIRS = [
    "_sys/claude/config/CLAUDE.md",
    "_sys/gemini/config/GEMINI.md",
    "_sys/docs-v2/user/",       # user-facing requirements may include Korean terms
    "_sys/data/",
    "_archive/",
    "Garbage/",
]

_INLINE_CODE_RE = re.compile(r"`[^`]+`")


def _inv19_exempt(path: Path) -> bool:
    rel = str(path.relative_to(_ROOT)).replace("\\", "/")
    for allowed in _INV19_KOREAN_ALLOWED_DIRS:
        if rel == allowed or rel.startswith(allowed):
            return True
    return False


def _strip_code(line: str, in_fence: bool) -> tuple[str, bool]:
    """Return (line_without_code, in_fence_after).
    Lines inside fenced blocks (```...```) are returned empty.
    Inline code (`...`) is stripped from the line.
    """
    stripped = line.strip()
    if stripped.startswith("```"):
        return "", not in_fence
    if in_fence:
        return "", True
    cleaned = _INLINE_CODE_RE.sub("", line)
    return cleaned, False


def chk_02_inv19_korean(exempt_paths: list[str]) -> list[Finding]:
    """No Korean characters in _sys/ docs (INV-19), except whitelisted files/dirs.
    Skips fenced code blocks and inline code (Korean in regex patterns is not a violation).
    """
    findings: list[Finding] = []
    scan_dirs = [_SYS_DIR / "docs-v2", _SYS_DIR / "ai", _SYS_DIR / "checks", _SYS_DIR / "core"]
    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for f in scan_dir.rglob("*.md"):
            if _is_exempt(f, exempt_paths) or _inv19_exempt(f):
                continue
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            in_fence = False
            for lineno, line in enumerate(lines, 1):
                cleaned, in_fence = _strip_code(line, in_fence)
                if cleaned and _HANGUL_RE.search(cleaned):
                    findings.append(Finding(
                        "CHK-02", "T3",
                        str(f.relative_to(_ROOT)).replace("\\", "/"),
                        lineno,
                        f"Korean text detected (INV-19): {line.strip()[:80]}",
                    ))
    return findings


# ── CHK-03: Coverage map (script→doc co-change) ───────────────────────────────

def chk_03_coverage_map(_exempt: list[str]) -> list[Finding]:
    """If a tracked Python script changed since last doc update, flag for doc co-change."""
    findings: list[Finding] = []
    try:
        result = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:", "-1", "HEAD"],
            capture_output=True, text=True, cwd=str(_ROOT),
        )
        changed = set(result.stdout.splitlines())
    except Exception:
        return findings

    _PY_DOC_EXEMPT_PREFIXES = ("_sys/tests/", "_sys/checks/self_care.py")
    py_changed = {
        f for f in changed
        if f.endswith(".py") and f.startswith("_sys/")
        and not any(f.startswith(p) for p in _PY_DOC_EXEMPT_PREFIXES)
    }
    doc_changed = {f for f in changed if f.endswith(".md") and f.startswith("_sys/docs-v2/")}

    if py_changed and not doc_changed:
        findings.append(Finding(
            "CHK-03", "T2", "commit:HEAD", 0,
            f"Python files changed without docs-v2/ update (Doc-as-Code): {sorted(py_changed)}",
        ))
    return findings


# ── CHK-04: Anchor integrity ──────────────────────────────────────────────────

def _extract_anchors(md_path: Path) -> set[str]:
    """Return set of lowercase slugified header anchors from a markdown file."""
    anchors = set()
    for line in md_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^#{1,6}\s+(.+)", line)
        if m:
            slug = re.sub(r"[^\w\s-]", "", m.group(1).lower()).strip()
            slug = re.sub(r"[\s]+", "-", slug)
            anchors.add(slug)
    return anchors


def chk_04_anchor_integrity(exempt_paths: list[str]) -> list[Finding]:
    """Internal markdown links with #anchor must reference an existing header."""
    findings: list[Finding] = []
    for md_file in _DOCS_DIR.rglob("*.md"):
        if _is_exempt(md_file, exempt_paths):
            continue
        content = md_file.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        for lineno, line in enumerate(lines, 1):
            for match in _ANCHOR_REF_RE.finditer(line):
                href = match.group(1)
                if "#" not in href or href.startswith("http"):
                    continue
                parts = href.split("#", 1)
                anchor = parts[1].lower()
                if parts[0]:
                    target_path = (_DOCS_DIR / parts[0].lstrip("/")).resolve()
                    if not target_path.exists():
                        continue  # CHK-01 already covers missing files
                else:
                    target_path = md_file

                if target_path.exists():
                    available = _extract_anchors(target_path)
                    if anchor and anchor not in available:
                        findings.append(Finding(
                            "CHK-04", "T2",
                            str(md_file.relative_to(_ROOT)).replace("\\", "/"),
                            lineno,
                            f"Broken anchor #{anchor} in {href}",
                        ))
    return findings


# ── CHK-05: Value sync (numeric constants vs protocol.json) ───────────────────

_VALUE_SYNC_TARGETS: dict[str, tuple[str, Any]] = {
    "collab_rate": ("collab_rate.current", None),
}


def chk_05_value_sync(_exempt: list[str]) -> list[Finding]:
    """Key numeric values in docs must match protocol.json SSOT."""
    findings: list[Finding] = []
    protocol = _load_json(_PROTOCOL_PATH)

    collab_current = protocol.get("collab_rate", {}).get("current")
    if collab_current is None:
        return findings

    docs_pattern = re.compile(r"collab_rate[:\s]+(\d+)")
    for md_file in _DOCS_DIR.rglob("*.md"):
        lines = md_file.read_text(encoding="utf-8", errors="replace").splitlines()
        for lineno, line in enumerate(lines, 1):
            for m in docs_pattern.finditer(line):
                val = int(m.group(1))
                if val != collab_current and val not in (0, 10):
                    findings.append(Finding(
                        "CHK-05", "T2",
                        str(md_file.relative_to(_ROOT)).replace("\\", "/"),
                        lineno,
                        f"collab_rate {val} in doc ≠ protocol.json current={collab_current}",
                    ))
    return findings


# ── CHK-06: Proposal TTL ──────────────────────────────────────────────────────

_PROPOSALS_DIR = _ROOT / "_archive" / "proposals" / "pending"
_TTL_DAYS = 14


def chk_06_proposal_ttl(_exempt: list[str]) -> list[Finding]:
    """Proposals older than TTL_DAYS that are still pending should be flagged."""
    findings: list[Finding] = []
    if not _PROPOSALS_DIR.exists():
        return findings

    now = datetime.now(timezone.utc)
    for f in _PROPOSALS_DIR.glob("*.md"):
        stat = f.stat()
        age_days = (now.timestamp() - stat.st_mtime) / 86400
        if age_days > _TTL_DAYS:
            findings.append(Finding(
                "CHK-06", "T1",
                str(f.relative_to(_ROOT)).replace("\\", "/"),
                0,
                f"Proposal pending {age_days:.0f} days (TTL={_TTL_DAYS}d): {f.name}",
            ))
    return findings


# ── CHK-07: Orphaned files ─────────────────────────────────────────────────────

_MANIFEST_PATH = _DOCS_DIR / "00-MANIFEST.md"


def chk_07_orphaned_files(_exempt: list[str]) -> list[Finding]:
    """docs-v2/ files not referenced in 00-MANIFEST.md should be flagged."""
    findings: list[Finding] = []
    if not _MANIFEST_PATH.exists():
        return findings

    manifest_text = _MANIFEST_PATH.read_text(encoding="utf-8")
    for md_file in _DOCS_DIR.rglob("*.md"):
        rel = str(md_file.relative_to(_DOCS_DIR)).replace("\\", "/")
        if rel == "00-MANIFEST.md":
            continue
        if rel not in manifest_text and f"`{rel}`" not in manifest_text:
            findings.append(Finding(
                "CHK-07", "T1",
                str(md_file.relative_to(_ROOT)).replace("\\", "/"),
                0,
                f"File not referenced in 00-MANIFEST.md: {rel}",
            ))
    return findings


# ── Runner ─────────────────────────────────────────────────────────────────────

_CHECK_MAP = {
    "CHK-01": chk_01_path_existence,
    "CHK-02": chk_02_inv19_korean,
    "CHK-03": chk_03_coverage_map,
    "CHK-04": chk_04_anchor_integrity,
    "CHK-05": chk_05_value_sync,
    "CHK-06": chk_06_proposal_ttl,
    "CHK-07": chk_07_orphaned_files,
}


def run_checks(
    check_ids: list[str],
    exempt_paths: list[str],
    fail_on: list[str],
    *,
    json_output: bool = False,
) -> int:
    all_findings: list[Finding] = []
    results: dict[str, dict] = {}

    for chk_id in check_ids:
        fn = _CHECK_MAP.get(chk_id)
        if fn is None:
            print(f"[WARN] Unknown check ID: {chk_id}", file=sys.stderr)
            continue
        try:
            findings = fn(exempt_paths)
        except Exception as exc:
            findings = [Finding(chk_id, "T3", "runner", 0, f"Check raised exception: {exc}")]

        all_findings.extend(findings)
        results[chk_id] = {
            "status": "FAIL" if findings else "PASS",
            "count": len(findings),
            "findings": [f.to_dict() for f in findings],
        }

    exit_code = 0
    for chk_id in fail_on:
        if results.get(chk_id, {}).get("status") == "FAIL":
            exit_code = 1

    if json_output:
        out = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "checks_run": check_ids,
            "exit_code": exit_code,
            "summary": {k: v["status"] for k, v in results.items()},
            "results": results,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        total = len(all_findings)
        fails = sum(1 for f in all_findings if f.tier in ("T3", "T4"))
        print(f"\n{'━'*60}")
        print(f"  check_docs_mece — {len(check_ids)} checks | {total} findings ({fails} T3+)")
        print(f"{'━'*60}")
        for chk_id, res in results.items():
            status_icon = "✓" if res["status"] == "PASS" else "✗"
            print(f"  {status_icon} {chk_id}: {res['status']} ({res['count']} findings)")
        if all_findings:
            print()
            for f in all_findings:
                print(f"  {f}")
        print(f"{'━'*60}")
        print(f"  Exit: {exit_code}")
        print()

    return exit_code


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="check_docs_mece — docs-v2 MECE validation")
    parser.add_argument(
        "--checks", default=None,
        help="Comma-separated check IDs (default: all enabled in governance_params.json)",
    )
    parser.add_argument("--fix", action="store_true", help="Auto-fix where possible (reserved)")
    parser.add_argument("--json", action="store_true", dest="json_out", help="JSON output")
    args = parser.parse_args()

    cfg = _load_config()
    check_ids = (
        [c.strip() for c in args.checks.split(",")]
        if args.checks else cfg["checks_enabled"]
    )

    return run_checks(
        check_ids,
        cfg["exempt_paths"],
        cfg["fail_on"],
        json_output=args.json_out,
    )


if __name__ == "__main__":
    sys.exit(main())
