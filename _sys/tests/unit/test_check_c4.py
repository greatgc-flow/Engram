"""
Unit Tests for Cluster C4 (Pre-Commit Check-Script Hardening — All 7 Items)

Covers:
  1. Staged-vs-worktree distinction (IndexView vs WorktreeView disagreement).
  2. Shared extract_local_markdown_links parser.
  3. CHK-02 INV-19 extension & # INV19-ALLOW: ... exemption line convention.
  4. CHK-03 git infrastructure error fail-closed behavior.
  5. CHK-CONST AST subscript chain verification & evasion rejection.
  6. CHK-LEDGER empty expected_substring non-empty requirement & structured error return.
  7. CHK-LEDGER json_array_member verification for T82 in backlog.json.
"""

import ast
import json
import pytest
from pathlib import Path

import sys
SYS_DIR = Path(__file__).parent.parent.parent.resolve()
CHECKS_DIR = SYS_DIR / "checks"
if str(CHECKS_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKS_DIR))

import _common
import check_docs_mece



class MockView:
    def __init__(self, files: dict[str, str]):
        self.files = {k.replace("\\", "/").lstrip("/"): v for k, v in files.items()}

    def list_files(self, prefix: str = "", suffix: str = "") -> list[str]:
        p = prefix.replace("\\", "/").lstrip("/")
        s = suffix.lower()
        res = []
        for path in self.files.keys():
            if p and not path.startswith(p):
                continue
            if s and not path.lower().endswith(s):
                continue
            res.append(path)
        return sorted(res)

    def exists(self, rel_path: str) -> bool:
        clean = rel_path.replace("\\", "/").lstrip("/")
        return clean in self.files

    def read_text(self, rel_path: str) -> str:
        clean = rel_path.replace("\\", "/").lstrip("/")
        if clean not in self.files:
            raise FileNotFoundError(rel_path)
        return self.files[clean]


# ── Item 1: Staged-vs-Worktree Distinction ─────────────────────────────────────

def test_staged_vs_worktree_disagreement():
    """Prove that IndexView and WorktreeView produce different check results when index & worktree disagree."""
    staged_files = {
        "_sys/docs-v2/test.md": "Link to deleted file: `_sys/core/deleted.py`",
        "_sys/docs-v2/00-MANIFEST.md": "`test.md`",
        "_sys/ai/protocol.json": json.dumps({"collab_rate": {"current": 100}}),
    }
    worktree_files = dict(staged_files)
    worktree_files["_sys/core/deleted.py"] = "# Unstaged file present in worktree but deleted in staged index"

    index_view = MockView(staged_files)
    worktree_view = MockView(worktree_files)

    # Check against index_view (staged index does NOT contain deleted.py) -> MUST FAIL (finding produced)
    staged_findings = check_docs_mece.chk_01_path_existence([], index_view)
    assert len(staged_findings) == 1
    assert "Referenced path not found: _sys/core/deleted.py" in staged_findings[0].message

    # Check against worktree_view (worktree still contains deleted.py) -> PASSES (0 findings)
    worktree_findings = check_docs_mece.chk_01_path_existence([], worktree_view)
    assert len(worktree_findings) == 0


# ── Item 2: Shared Markdown Link Extractor ────────────────────────────────────

def test_extract_local_markdown_links():
    text = """
    Inline link: [Gov](_sys/docs-v2/ops/governance.md#1-1?v=2)
    Angle bracket: <_sys/docs-v2/ops/protocol.md#sec-2>
    Reference: [ref]: _sys/ai/routing-config.json?debug=true
    External web: [Google](https://google.com)
    Mailto: <mailto:test@example.com>
    """
    links = _common.extract_local_markdown_links(text)
    assert len(links) == 3

    assert links[0][2] == "_sys/docs-v2/ops/governance.md"
    assert links[1][2] == "_sys/docs-v2/ops/protocol.md"
    assert links[2][2] == "_sys/ai/routing-config.json"


# ── Item 3: CHK-02 INV-19 Scope Extension & # INV19-ALLOW Exemption ──────────

def test_chk_02_inv19_code_extension_and_exemption(monkeypatch):
    # .py/.json/.sh scanning is opt-in (governance_params.json's
    # docs_mece_inv19_scan_extensions), defaulting to .md-only, since real
    # pre-existing Korean console output (e.g. _sys/core/scrubber.py) has not
    # been through an # INV19-ALLOW tagging sweep yet -- enabling it by
    # default would fail every future commit on pre-existing debt. This test
    # exercises the capability directly, as governance would once opted in.
    monkeypatch.setattr(check_docs_mece, "_INV19_SCAN_EXTENSIONS", (".md", ".py", ".json", ".sh"))
    files = {
        # Python code file with untagged Hangul -> SHOULD FAIL
        "_sys/core/bad.py": 'msg = "한글 테스트"\n',
        # Python code file with # INV19-ALLOW: HUMAN_CONSOLE -> SHOULD PASS
        "_sys/core/good.py": 'msg = "한글 콘솔"  # INV19-ALLOW: HUMAN_CONSOLE\n',
        # Shell script with untagged Hangul -> SHOULD FAIL
        "_sys/checks/bad.sh": 'echo "한글"\n',
        # Shell script with # INV19-ALLOW: ... -> SHOULD PASS
        "_sys/checks/good.sh": 'echo "한글" # INV19-ALLOW: SHELL_OUTPUT\n',
    }
    view = MockView(files)
    findings = check_docs_mece.chk_02_inv19_korean([], view)

    finding_paths = {f.path for f in findings}
    assert "_sys/core/bad.py" in finding_paths
    assert "_sys/checks/bad.sh" in finding_paths
    assert "_sys/core/good.py" not in finding_paths
    assert "_sys/checks/good.sh" not in finding_paths


# ── Item 4: CHK-03 Fail-Closed on Git Error ───────────────────────────────────

def test_chk_03_git_error_fails_closed(monkeypatch):
    """Git infrastructure error must return T3 finding (FAIL CLOSED)."""
    import subprocess
    def mock_run(*args, **kwargs):
        raise subprocess.SubprocessError("Git execution failed")

    monkeypatch.setattr(subprocess, "run", mock_run)
    view = MockView({})
    findings = check_docs_mece.chk_03_coverage_map([], view)

    assert len(findings) == 1
    assert findings[0].tier == "T3"
    assert "Git infrastructure error" in findings[0].message

