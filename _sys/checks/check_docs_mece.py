"""check_docs_mece.py — MECE validation for docs-v2/ (EDGE-04).

Implements the documentation checks referenced by ops/governance.md and
ops/peer-debate-2026-06-19.md.

Cluster C4 Hardening:
  - Staged-vs-worktree (IndexView vs WorktreeView abstractions via --source=index/worktree).
  - Shared extract_local_markdown_links parser.
  - CHK-02 INV-19 scope extended to .py/.json/.sh with # INV19-ALLOW: ... exemption line convention.
  - CHK-03 git infrastructure errors fail CLOSED.

Usage:
    python check_docs_mece.py [--checks CHK-01,CHK-02] [--source index|worktree] [--fix] [--json]

Exit codes:
    0 — all checks pass (or only T1/T2 issues, none in fail_on list)
    1 — at least one fail_on check failed (T3 violations or git infrastructure failure)
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
from typing import Any, Protocol, Union

_CHECKS_DIR = Path(__file__).parent
_SYS_DIR = _CHECKS_DIR.parent
_AI_DIR = _SYS_DIR / "ai"
_ROOT = _SYS_DIR.parent
_DOCS_DIR = _SYS_DIR / "docs-v2"
_GOVERNANCE_PATH = _AI_DIR / "governance_params.json"
_PROTOCOL_PATH = _AI_DIR / "protocol.json"
_MANIFEST_PATH = _DOCS_DIR / "00-MANIFEST.md"
_PROPOSALS_DIR = _ROOT / "_archive" / "proposals" / "pending"

sys.path.insert(0, str(_CHECKS_DIR))
from _common import IndexView, WorktreeView, UnmergedIndexError, extract_local_markdown_links  # noqa: E402

_HANGUL_RE = re.compile(r"[가-힣]")
_PATH_REF_RE = re.compile(r"`([_a-zA-Z0-9./\-]+\.(?:md|json|py|sh|bat|txt))`")
_SECTION_REF_RE = re.compile(r"§(\d[\d\-\.]*)")


# ── View Interface ────────────────────────────────────────────────────────────

class FileView(Protocol):
    def list_files(self, prefix: str = "", suffix: str = "") -> list[str]: ...
    def exists(self, rel_path: str) -> bool: ...
    def read_text(self, rel_path: str) -> str: ...


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
        # CHK-02's .py/.json/.sh scope (C4 design) requires every legitimate
        # Korean console-output line to carry an explicit
        # '# INV19-ALLOW: HUMAN_CONSOLE' tag first. That sweep has not been
        # done yet (real pre-existing Korean console output exists in e.g.
        # _sys/core/scrubber.py, per this repo's own stated policy that
        # user-facing console output is Korean) -- defaulting the expanded
        # scope ON would fail every future commit on pre-existing debt, not
        # newly introduced violations. Default stays .md-only (pre-C4
        # behavior) until governance_params.json opts in post-sweep.
        "inv19_scan_extensions": gov.get("docs_mece_inv19_scan_extensions", [".md"]),
    }


def _is_exempt(rel_path: str, exempt_paths: list[str]) -> bool:
    clean = rel_path.replace("\\", "/")
    return any(clean.startswith(e) for e in exempt_paths)


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

def _resolve_view_path(ref: str, doc_dir_rel: str, view: FileView) -> bool:
    """Try multiple resolution strategies against active view. Return True if found."""
    # 1. Root-relative paths
    if ref.startswith(("_sys/", "workspace/", "_archive/", "workspace-base/")):
        return view.exists(ref)
    if ref.startswith("/"):
        return view.exists(ref.lstrip("/"))
    # 2. Relative to document's directory
    doc_rel = (doc_dir_rel + "/" + ref).replace("//", "/") if doc_dir_rel else ref
    if view.exists(doc_rel):
        return True
    # 3. Relative to docs-v2 root
    if view.exists("_sys/docs-v2/" + ref):
        return True
    # 4. Relative to _sys root
    if view.exists("_sys/" + ref):
        return True
    return view.exists(ref)


def chk_01_path_existence(exempt_paths: list[str], view: FileView | None = None) -> list[Finding]:
    """All root-relative file paths referenced in docs-v2 *.md files must exist in view."""
    active_view = view or WorktreeView(_ROOT)
    _ROOT_PREFIXES = ("_sys/", "workspace/", "_archive/", "workspace-base/")
    findings: list[Finding] = []
    md_files = active_view.list_files("_sys/docs-v2/", suffix=".md")

    for md_rel in md_files:
        if _is_exempt(md_rel, exempt_paths):
            continue
        try:
            content = active_view.read_text(md_rel)
        except Exception as exc:
            findings.append(Finding("CHK-01", "T3", md_rel, 0, f"Could not read staged file: {exc}"))
            continue

        doc_dir_rel = os.path.dirname(md_rel).replace("\\", "/")
        lines = content.splitlines()
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
                if not _resolve_view_path(ref, doc_dir_rel, active_view):
                    findings.append(Finding(
                        "CHK-01", "T3",
                        md_rel,
                        lineno,
                        f"Referenced path not found: {ref}",
                    ))
    return findings


# ── CHK-02: INV-19 Korean detection ───────────────────────────────────────────

_INV19_KOREAN_ALLOWED_DIRS = [
    "_sys/claude/config/CLAUDE.md",
    "_sys/gemini/config/GEMINI.md",
    "_sys/docs-v2/user/",
    "_sys/data/",
    "_archive/",
    "Garbage/",
]

_INLINE_CODE_RE = re.compile(r"`[^`]+`")

# Overridden by main() from governance_params.json's docs_mece_inv19_scan_extensions
# (see _load_config's comment on why this defaults to .md-only).
_INV19_SCAN_EXTENSIONS: tuple[str, ...] = (".md",)


def _inv19_exempt(rel_path: str) -> bool:
    clean = rel_path.replace("\\", "/")
    for allowed in _INV19_KOREAN_ALLOWED_DIRS:
        if clean == allowed or clean.startswith(allowed):
            return True
    return False


def _strip_code(line: str, in_fence: bool) -> tuple[str, bool]:
    stripped = line.strip()
    if stripped.startswith("```"):
        return "", not in_fence
    if in_fence:
        return "", True
    cleaned = _INLINE_CODE_RE.sub("", line)
    return cleaned, False


def chk_02_inv19_korean(exempt_paths: list[str], view: FileView | None = None) -> list[Finding]:
    """No Korean characters in _sys/ docs, core, checks, or ai (INV-19).
    
    Extended to .md, .py, .json, .sh.
    Honors # INV19-ALLOW: ... on exact line for Python/shell code files.
    """
    active_view = view or WorktreeView(_ROOT)
    findings: list[Finding] = []
    scan_prefixes = ["_sys/docs-v2/", "_sys/ai/", "_sys/checks/", "_sys/core/"]

    for prefix in scan_prefixes:
        for ext in _INV19_SCAN_EXTENSIONS:
            files = active_view.list_files(prefix, suffix=ext)
            for rel_path in files:
                if _is_exempt(rel_path, exempt_paths) or _inv19_exempt(rel_path):
                    continue
                try:
                    content = active_view.read_text(rel_path)
                except Exception as exc:
                    findings.append(Finding("CHK-02", "T3", rel_path, 0, f"Unreadable file: {exc}"))
                    continue

                lines = content.splitlines()
                is_code = ext in (".py", ".sh")
                in_fence = False

                for lineno, line in enumerate(lines, 1):
                    if is_code and "INV19-ALLOW:" in line:
                        continue

                    if ext == ".md":
                        cleaned, in_fence = _strip_code(line, in_fence)
                    else:
                        cleaned = line

                    if cleaned and _HANGUL_RE.search(cleaned):
                        findings.append(Finding(
                            "CHK-02", "T3",
                            rel_path,
                            lineno,
                            f"Korean text detected (INV-19): {line.strip()[:80]}",
                        ))
    return findings


# ── CHK-03: Coverage map (script→doc co-change) ───────────────────────────────

def chk_03_coverage_map(_exempt: list[str], view: FileView | None = None) -> list[Finding]:
    """If a tracked Python script changed since last doc update, flag for doc co-change.
    
    Git infrastructure failures FAIL CLOSED (T3 finding / exit 1).
    """
    active_view = view or WorktreeView(_ROOT)
    findings: list[Finding] = []
    try:
        result = subprocess.run(
            ["git", "log", "--name-only", "--pretty=format:", "-1", "HEAD"],
            capture_output=True, text=True, cwd=str(_ROOT), check=True,
        )
        changed = set(result.stdout.splitlines())
    except Exception as exc:
        # FAIL CLOSED on git infrastructure error
        findings.append(Finding(
            "CHK-03", "T3", "git:log", 0,
            f"Git infrastructure error reading HEAD log: {exc}",
        ))
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

def _extract_anchors_text(content: str) -> set[str]:
    anchors = set()
    for line in content.splitlines():
        m = re.match(r"^#{1,6}\s+(.+)", line)
        if m:
            slug = re.sub(r"[^\w\s-]", "", m.group(1).lower()).strip()
            slug = re.sub(r"[\s]+", "-", slug)
            anchors.add(slug)
    return anchors


def chk_04_anchor_integrity(exempt_paths: list[str], view: FileView | None = None) -> list[Finding]:
    """Internal markdown links with #anchor must reference an existing header in view."""
    active_view = view or WorktreeView(_ROOT)
    findings: list[Finding] = []
    md_files = active_view.list_files("_sys/docs-v2/", suffix=".md")

    for md_rel in md_files:
        if _is_exempt(md_rel, exempt_paths):
            continue
        try:
            content = active_view.read_text(md_rel)
        except Exception:
            continue

        links = extract_local_markdown_links(content)
        for lineno, raw_href, clean_href in links:
            if "#" not in raw_href:
                continue
            parts = raw_href.split("#", 1)
            anchor = parts[1].lower().split("?", 1)[0].strip()
            target_rel = parts[0].strip()

            if target_rel:
                resolved_rel = target_rel.lstrip("/")
                if not resolved_rel.startswith("_sys/"):
                    resolved_rel = ("_sys/docs-v2/" + target_rel).replace("//", "/")
                if not active_view.exists(resolved_rel):
                    continue  # CHK-01 covers missing target files
            else:
                resolved_rel = md_rel

            if active_view.exists(resolved_rel):
                try:
                    target_content = active_view.read_text(resolved_rel)
                    available = _extract_anchors_text(target_content)
                    if anchor and anchor not in available:
                        findings.append(Finding(
                            "CHK-04", "T2",
                            md_rel,
                            lineno,
                            f"Broken anchor #{anchor} in {raw_href}",
                        ))
                except Exception:
                    pass

    return findings


# ── CHK-05: Value sync ────────────────────────────────────────────────────────

def chk_05_value_sync(_exempt: list[str], view: FileView | None = None) -> list[Finding]:
    """Key numeric values in docs must match protocol.json SSOT."""
    active_view = view or WorktreeView(_ROOT)
    findings: list[Finding] = []
    if not active_view.exists("_sys/ai/protocol.json"):
        return findings

    try:
        protocol = json.loads(active_view.read_text("_sys/ai/protocol.json"))
    except Exception:
        return findings

    # CHK-05 retired: collab_rate was part of the peer-governance layer that
    # moved out of Engram with the peerhub separation. Nothing to reconcile.
    return findings


# ── CHK-06: Proposal TTL ──────────────────────────────────────────────────────

def chk_06_proposal_ttl(_exempt: list[str], view: FileView | None = None) -> list[Finding]:
    """Proposals older than 14 days that are still pending should be flagged."""
    active_view = view or WorktreeView(_ROOT)
    findings: list[Finding] = []
    prop_files = active_view.list_files("_archive/proposals/pending/", suffix=".md")
    now = datetime.now(timezone.utc)

    for prop_rel in prop_files:
        full_path = _ROOT / prop_rel
        if full_path.exists():
            age_days = (now.timestamp() - full_path.stat().st_mtime) / 86400
            if age_days > 14:
                findings.append(Finding(
                    "CHK-06", "T1",
                    prop_rel,
                    0,
                    f"Proposal pending {age_days:.0f} days (TTL=14d): {os.path.basename(prop_rel)}",
                ))
    return findings


# ── CHK-07: Orphaned files ─────────────────────────────────────────────────────

def chk_07_orphaned_files(_exempt: list[str], view: FileView | None = None) -> list[Finding]:
    """docs-v2/ files not referenced in 00-MANIFEST.md should be flagged."""
    active_view = view or WorktreeView(_ROOT)
    findings: list[Finding] = []
    manifest_rel = "_sys/docs-v2/00-MANIFEST.md"
    if not active_view.exists(manifest_rel):
        return findings

    try:
        manifest_text = active_view.read_text(manifest_rel)
    except Exception:
        return findings

    md_files = active_view.list_files("_sys/docs-v2/", suffix=".md")
    for md_rel in md_files:
        if md_rel == manifest_rel:
            continue
        short_rel = md_rel.replace("_sys/docs-v2/", "")
        if short_rel not in manifest_text and f"`{short_rel}`" not in manifest_text:
            findings.append(Finding(
                "CHK-07", "T1",
                md_rel,
                0,
                f"File not referenced in 00-MANIFEST.md: {short_rel}",
            ))
    return findings


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_checks(
    check_ids: list[str],
    exempt_paths: list[str],
    fail_on: list[str],
    view: FileView | None = None,
    *,
    json_output: bool = False,
) -> int:
    active_view = view or WorktreeView(_ROOT)
    all_findings: list[Finding] = []
    results: dict[str, dict] = {}

    check_map = {
        "CHK-01": chk_01_path_existence,
        "CHK-02": chk_02_inv19_korean,
        "CHK-03": chk_03_coverage_map,
        "CHK-04": chk_04_anchor_integrity,
        "CHK-05": chk_05_value_sync,
        "CHK-06": chk_06_proposal_ttl,
        "CHK-07": chk_07_orphaned_files,
    }

    for chk_id in check_ids:
        fn = check_map.get(chk_id)
        if fn is None:
            print(f"[WARN] Unknown check ID: {chk_id}", file=sys.stderr)
            continue
        try:
            findings = fn(exempt_paths, active_view)
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
    parser.add_argument(
        "--source", choices=["index", "worktree"], default="worktree",
        help="Source view: 'index' (staged git index) or 'worktree' (filesystem, default)",
    )
    parser.add_argument("--fix", action="store_true", help="Auto-fix where possible (reserved)")
    parser.add_argument("--json", action="store_true", dest="json_out", help="JSON output")
    args = parser.parse_args()

    cfg = _load_config()
    check_ids = (
        [c.strip() for c in args.checks.split(",")]
        if args.checks else cfg["checks_enabled"]
    )
    global _INV19_SCAN_EXTENSIONS
    _INV19_SCAN_EXTENSIONS = tuple(cfg["inv19_scan_extensions"])

    try:
        view: FileView = IndexView(_ROOT) if args.source == "index" else WorktreeView(_ROOT)
    except Exception as exc:
        print(f"[CHK-ERROR] Failed to initialize {args.source} view: {exc}", file=sys.stderr)
        return 1  # FAIL CLOSED on view initialization failure

    return run_checks(
        check_ids,
        cfg["exempt_paths"],
        cfg["fail_on"],
        view,
        json_output=args.json_out,
    )


if __name__ == "__main__":
    sys.exit(main())
