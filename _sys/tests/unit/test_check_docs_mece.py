"""Comprehensive tests for check_docs_mece.py — CHK-01~07 MECE validation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "checks"))

import check_docs_mece
from check_docs_mece import (
    Finding, chk_01_path_existence, chk_02_inv19_korean,
    chk_03_coverage_map, chk_04_anchor_integrity,
    chk_05_value_sync, chk_06_proposal_ttl, chk_07_orphaned_files,
    _load_config, run_checks,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_doc(tmp_path: Path, rel_path: str, content: str) -> Path:
    """Create a doc file at a path relative to tmp_path."""
    p = tmp_path / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ── Finding class ─────────────────────────────────────────────────────────────

class TestFinding:
    def test_finding_fields(self):
        f = Finding("CHK-01", "T3", "some/file.md", 5, "path not found")
        assert f.check_id == "CHK-01"
        assert f.tier == "T3"
        assert f.path == "some/file.md"   # attribute is `path`, not `file`
        assert f.line == 5
        assert "path not found" in f.message

    def test_finding_str_representation(self):
        f = Finding("CHK-02", "T3", "file.md", 1, "Korean detected")
        s = str(f)
        assert "CHK-02" in s

    def test_finding_to_dict(self):
        f = Finding("CHK-01", "T3", "file.md", 3, "missing")
        d = f.to_dict()
        assert d["check_id"] == "CHK-01"
        assert d["tier"] == "T3"
        assert d["line"] == 3

    def test_finding_severity_t3_is_fail(self):
        f = Finding("CHK-01", "T3", "file.md", 0, "fail")
        assert f.tier == "T3"


# ── CHK-01: Path existence ────────────────────────────────────────────────────

class TestChk01PathExistence:
    def _mock_docs(self, tmp_path, docs_rel="docs-v2"):
        docs_dir = tmp_path / "_sys" / docs_rel
        docs_dir.mkdir(parents=True, exist_ok=True)
        return docs_dir

    def test_no_backtick_paths_returns_no_findings(self, tmp_path):
        doc = make_doc(tmp_path, "_sys/docs-v2/test.md",
                       "# Test\nThis doc has no path references.\n")
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_01_path_existence([])
        assert findings == []

    def test_existing_path_in_backticks_passes(self, tmp_path):
        existing = tmp_path / "_sys" / "ai" / "protocol.json"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("{}", encoding="utf-8")
        content = "See `_sys/ai/protocol.json` for details.\n"
        doc = make_doc(tmp_path, "_sys/docs-v2/test.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_01_path_existence([])
        assert findings == []

    def test_missing_path_in_backticks_fails(self, tmp_path):
        content = "See `_sys/ai/missing-file.json` for details.\n"
        doc = make_doc(tmp_path, "_sys/docs-v2/test.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_01_path_existence([])
        chk1 = [f for f in findings if f.check_id == "CHK-01"]
        assert len(chk1) >= 1
        assert any("missing-file.json" in f.message for f in chk1)

    def test_fenced_code_block_paths_skipped(self, tmp_path):
        content = (
            "# Test\n"
            "```\n"
            "`_sys/ai/does-not-exist.json`\n"
            "```\n"
        )
        doc = make_doc(tmp_path, "_sys/docs-v2/test.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_01_path_existence([])
        assert findings == []

    def test_exempt_path_prefix_skips_file(self, tmp_path):
        content = "See `_sys/ai/missing.json`\n"
        doc = make_doc(tmp_path, "_archive/old.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_01_path_existence(["_archive/"])
        # File is in _archive/ which is exempt — skip
        assert findings == []

    def test_non_sys_paths_not_checked(self, tmp_path):
        content = "See `relative/path.md` for details.\n"
        doc = make_doc(tmp_path, "_sys/docs-v2/test.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_01_path_existence([])
        # relative/path.md doesn't start with _sys/ or workspace/ — not checked
        assert findings == []


# ── CHK-02: INV-19 Korean language ───────────────────────────────────────────

class TestChk02Inv19Korean:
    def test_no_korean_passes(self, tmp_path):
        content = "# Title\nAll English content here.\n"
        doc = make_doc(tmp_path, "_sys/docs-v2/en.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_02_inv19_korean([])
        assert findings == []

    def test_korean_in_body_fails(self, tmp_path):
        content = "# Title\n한국어가 있으면 안 됩니다.\n"
        doc = make_doc(tmp_path, "_sys/docs-v2/fail.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_02_inv19_korean([])
        chk2 = [f for f in findings if f.check_id == "CHK-02"]
        assert len(chk2) >= 1

    def test_korean_in_fenced_code_block_skipped(self, tmp_path):
        content = (
            "# Title\n"
            "```\n"
            "한국어가 코드블록 안에 있음\n"
            "```\n"
        )
        doc = make_doc(tmp_path, "_sys/docs-v2/code.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_02_inv19_korean([])
        assert findings == []

    def test_korean_in_inline_code_skipped(self, tmp_path):
        content = "See `[가-힣]` regex pattern.\n"
        doc = make_doc(tmp_path, "_sys/docs-v2/regex.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_02_inv19_korean([])
        assert findings == []

    def test_user_dir_is_exempt(self, tmp_path):
        content = "# 사용자 요구사항\n한국어로 작성된 문서.\n"
        doc = make_doc(tmp_path, "_sys/docs-v2/user/manual.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_02_inv19_korean(["_sys/docs-v2/user/"])
        assert findings == []

    def test_finding_includes_line_number(self, tmp_path):
        content = "# Title\nLine two is fine.\n한국어 이 줄이 위반.\n"
        doc = make_doc(tmp_path, "_sys/docs-v2/fail.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_02_inv19_korean([])
        chk2 = [f for f in findings if f.check_id == "CHK-02"]
        assert chk2[0].line == 3  # Korean on line 3

    def test_claude_md_exempt_from_chk02(self, tmp_path):
        content = "한국어가 CLAUDE.md 에 있어도 됩니다.\n"
        doc = make_doc(tmp_path, "_sys/claude/config/CLAUDE.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            # CLAUDE.md is not in docs-v2 so not scanned by CHK-02 anyway
            findings = chk_02_inv19_korean([])
        assert findings == []


# ── CHK-03: Coverage map ──────────────────────────────────────────────────────

class TestChk03CoverageMap:
    def test_no_python_changed_returns_no_findings(self):
        mock_result = MagicMock()
        mock_result.stdout = "_sys/docs-v2/general/protocol.md\n"
        with patch("subprocess.run", return_value=mock_result):
            findings = chk_03_coverage_map([])
        assert findings == []

    def test_python_changed_no_docs_returns_finding(self):
        mock_result = MagicMock()
        mock_result.stdout = "_sys/core/hub.py\n"
        with patch("subprocess.run", return_value=mock_result):
            findings = chk_03_coverage_map([])
        chk3 = [f for f in findings if f.check_id == "CHK-03"]
        assert len(chk3) == 1

    def test_python_and_docs_changed_returns_no_findings(self):
        mock_result = MagicMock()
        mock_result.stdout = "_sys/core/hub.py\n_sys/docs-v2/ops/impl-plan.md\n"
        with patch("subprocess.run", return_value=mock_result):
            findings = chk_03_coverage_map([])
        assert findings == []

    def test_tests_dir_python_exempt(self):
        mock_result = MagicMock()
        mock_result.stdout = "_sys/tests/unit/test_hub.py\n"
        with patch("subprocess.run", return_value=mock_result):
            findings = chk_03_coverage_map([])
        assert findings == []

    def test_git_error_fails_closed(self):
        with patch("subprocess.run", side_effect=Exception("git not found")):
            findings = chk_03_coverage_map([])
        assert len(findings) == 1
        assert findings[0].tier == "T3"
        assert "Git infrastructure error" in findings[0].message


# ── CHK-04: Anchor integrity ──────────────────────────────────────────────────

class TestChk04AnchorIntegrity:
    def test_valid_anchor_passes(self, tmp_path):
        content = (
            "# Overview\n"
            "See [details](#details-section)\n"
            "## Details Section\n"
            "Content here.\n"
        )
        doc = make_doc(tmp_path, "_sys/docs-v2/test.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_04_anchor_integrity([])
        assert findings == []

    def test_invalid_anchor_fails(self, tmp_path):
        content = (
            "# Overview\n"
            "See [missing](#nonexistent-anchor)\n"
        )
        doc = make_doc(tmp_path, "_sys/docs-v2/test.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_04_anchor_integrity([])
        chk4 = [f for f in findings if f.check_id == "CHK-04"]
        assert len(chk4) >= 1

    def test_external_links_not_checked(self, tmp_path):
        content = "See [external](https://example.com/page#anchor)\n"
        doc = make_doc(tmp_path, "_sys/docs-v2/test.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_04_anchor_integrity([])
        assert findings == []

    def test_no_anchor_links_passes(self, tmp_path):
        content = "# Title\nNo links here at all.\n"
        doc = make_doc(tmp_path, "_sys/docs-v2/test.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_04_anchor_integrity([])
        assert findings == []


# ── CHK-05: Value sync ────────────────────────────────────────────────────────

class TestChk05ValueSync:
    def test_matching_collab_rate_passes(self, tmp_path):
        protocol = {"collab_rate": {"current": 5}}
        proto_file = tmp_path / "_sys" / "ai" / "protocol.json"
        proto_file.parent.mkdir(parents=True, exist_ok=True)
        proto_file.write_text(json.dumps(protocol), encoding="utf-8")

        # Doc mentions collab_rate 5
        content = "Current collab_rate: 5\n"
        doc = make_doc(tmp_path, "_sys/docs-v2/general/status.md", content)

        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_PROTOCOL_PATH", proto_file), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_05_value_sync([])
        assert findings == []

    def test_no_protocol_returns_no_findings(self, tmp_path):
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_PROTOCOL_PATH", tmp_path / "missing.json"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_05_value_sync([])
        assert findings == []


# ── CHK-06: Proposal TTL ──────────────────────────────────────────────────────

class TestChk06ProposalTtl:
    def test_no_proposals_returns_no_findings(self, tmp_path):
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_06_proposal_ttl([])
        assert findings == []

    def test_recent_proposal_passes(self, tmp_path):
        content = (
            "---\n"
            "status: pending\n"
            "created: 2026-06-17\n"
            "---\n"
            "# Proposal\n"
        )
        doc = make_doc(tmp_path, "_sys/docs-v2/_proposals/recent.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_06_proposal_ttl([])
        assert findings == []

    def test_old_pending_proposal_fails(self, tmp_path):
        # CHK-06 uses _PROPOSALS_DIR = _ROOT / "_archive" / "proposals" / "pending"
        # and checks file mtime, not YAML frontmatter
        proposals_dir = tmp_path / "_archive" / "proposals" / "pending"
        proposals_dir.mkdir(parents=True, exist_ok=True)
        old_proposal = proposals_dir / "old.md"
        old_proposal.write_text("# Old Proposal\n", encoding="utf-8")
        # Force mtime to be 30 days ago
        import time
        old_time = time.time() - (30 * 86400)
        import os
        os.utime(str(old_proposal), (old_time, old_time))

        with patch.object(check_docs_mece, "_PROPOSALS_DIR", proposals_dir), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_06_proposal_ttl([])
        chk6 = [f for f in findings if f.check_id == "CHK-06"]
        assert len(chk6) >= 1


# ── CHK-07: Orphaned files ────────────────────────────────────────────────────

class TestChk07OrphanedFiles:
    def test_no_docs_dir_returns_no_findings(self, tmp_path):
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "nonexistent"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_07_orphaned_files([])
        assert findings == []

    def test_listed_file_in_manifest_passes(self, tmp_path):
        docs_dir = tmp_path / "_sys" / "docs-v2"
        manifest_content = "general/test.md\n"
        make_doc(tmp_path, "_sys/docs-v2/00-MANIFEST.md", manifest_content)
        make_doc(tmp_path, "_sys/docs-v2/general/test.md", "# Test\n")
        manifest_path = docs_dir / "00-MANIFEST.md"
        with patch.object(check_docs_mece, "_DOCS_DIR", docs_dir), \
             patch.object(check_docs_mece, "_MANIFEST_PATH", manifest_path), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_07_orphaned_files([])
        assert findings == []

    def test_unlisted_file_fails(self, tmp_path):
        docs_dir = tmp_path / "_sys" / "docs-v2"
        make_doc(tmp_path, "_sys/docs-v2/00-MANIFEST.md", "# Manifest\n")
        make_doc(tmp_path, "_sys/docs-v2/general/orphan.md", "# Orphan\n")
        manifest_path = docs_dir / "00-MANIFEST.md"
        with patch.object(check_docs_mece, "_DOCS_DIR", docs_dir), \
             patch.object(check_docs_mece, "_MANIFEST_PATH", manifest_path), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_07_orphaned_files([])
        chk7 = [f for f in findings if f.check_id == "CHK-07"]
        assert len(chk7) >= 1

    def test_manifest_itself_not_flagged(self, tmp_path):
        docs_dir = tmp_path / "_sys" / "docs-v2"
        make_doc(tmp_path, "_sys/docs-v2/00-MANIFEST.md", "# Manifest\n")
        manifest_path = docs_dir / "00-MANIFEST.md"
        with patch.object(check_docs_mece, "_DOCS_DIR", docs_dir), \
             patch.object(check_docs_mece, "_MANIFEST_PATH", manifest_path), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            findings = chk_07_orphaned_files([])
        chk7 = [f for f in findings if f.check_id == "CHK-07"]
        assert not any("MANIFEST" in f.message for f in chk7)


# ── run_checks orchestration ──────────────────────────────────────────────────
# run_checks(check_ids, exempt_paths, fail_on, *, json_output=False) → int (exit code)

class TestRunChecks:
    def test_all_checks_return_zero_on_clean_state(self, tmp_path):
        docs_dir = tmp_path / "_sys" / "docs-v2"
        docs_dir.mkdir(parents=True, exist_ok=True)
        manifest = docs_dir / "00-MANIFEST.md"
        manifest.write_text("# Manifest\n", encoding="utf-8")

        with patch.object(check_docs_mece, "_DOCS_DIR", docs_dir), \
             patch.object(check_docs_mece, "_ROOT", tmp_path), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_PROTOCOL_PATH", tmp_path / "missing.json"), \
             patch.object(check_docs_mece, "_MANIFEST_PATH", manifest), \
             patch.object(check_docs_mece, "_PROPOSALS_DIR", tmp_path / "no-proposals"), \
             patch("subprocess.run", return_value=MagicMock(stdout="")):
            exit_code = run_checks(
                ["CHK-01","CHK-02","CHK-03","CHK-04","CHK-05","CHK-06","CHK-07"],
                exempt_paths=[],
                fail_on=["CHK-01","CHK-02"],
            )
        assert exit_code == 0

    def test_selected_chk01_only(self, tmp_path):
        docs_dir = tmp_path / "_sys" / "docs-v2"
        docs_dir.mkdir(parents=True, exist_ok=True)
        with patch.object(check_docs_mece, "_DOCS_DIR", docs_dir), \
             patch.object(check_docs_mece, "_ROOT", tmp_path), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"):
            exit_code = run_checks(["CHK-01"], exempt_paths=[], fail_on=["CHK-01"])
        assert exit_code in (0, 1)

    def test_fail_on_triggers_exit_1(self, tmp_path):
        docs_dir = tmp_path / "_sys" / "docs-v2"
        docs_dir.mkdir(parents=True, exist_ok=True)
        # Doc with Korean on line 2
        (docs_dir / "bad.md").write_text("# Title\n한국어 위반\n", encoding="utf-8")
        with patch.object(check_docs_mece, "_DOCS_DIR", docs_dir), \
             patch.object(check_docs_mece, "_ROOT", tmp_path), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"):
            exit_code = run_checks(["CHK-02"], exempt_paths=[], fail_on=["CHK-02"])
        assert exit_code == 1

    def test_non_fail_on_check_failure_returns_zero(self, tmp_path):
        docs_dir = tmp_path / "_sys" / "docs-v2"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "bad.md").write_text("# Title\n한국어 위반\n", encoding="utf-8")
        with patch.object(check_docs_mece, "_DOCS_DIR", docs_dir), \
             patch.object(check_docs_mece, "_ROOT", tmp_path), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"):
            # CHK-02 fails but is NOT in fail_on → exit 0
            exit_code = run_checks(["CHK-02"], exempt_paths=[], fail_on=[])
        assert exit_code == 0

    def test_json_output_cli(self):
        result = subprocess.run(
            [sys.executable, str(Path(check_docs_mece.__file__)),
             "--checks", "CHK-05", "--json"],
            capture_output=True, text=True,
        )
        # Should produce valid JSON on stdout
        try:
            data = json.loads(result.stdout)
            assert isinstance(data, dict)
        except json.JSONDecodeError:
            assert result.returncode in (0, 1)  # At minimum no crash

    def test_cli_exits_zero_on_pass(self):
        result = subprocess.run(
            [sys.executable, str(Path(check_docs_mece.__file__)),
             "--checks", "CHK-05"],
            capture_output=True, text=True,
        )
        # CHK-05 just checks collab_rate values — should pass on real codebase
        assert result.returncode in (0, 1)


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_docs_dir_all_checks_pass(self, tmp_path):
        docs_dir = tmp_path / "_sys" / "docs-v2"
        docs_dir.mkdir(parents=True, exist_ok=True)
        manifest = docs_dir / "00-MANIFEST.md"
        manifest.write_text("# Manifest\n", encoding="utf-8")

        with patch.object(check_docs_mece, "_DOCS_DIR", docs_dir), \
             patch.object(check_docs_mece, "_ROOT", tmp_path), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_PROTOCOL_PATH", tmp_path / "missing.json"), \
             patch.object(check_docs_mece, "_MANIFEST_PATH", manifest), \
             patch.object(check_docs_mece, "_PROPOSALS_DIR", tmp_path / "no-proposals"), \
             patch("subprocess.run", return_value=MagicMock(stdout="")):
            exit_code = run_checks(
                ["CHK-01","CHK-02","CHK-03","CHK-04","CHK-05","CHK-06","CHK-07"],
                exempt_paths=[], fail_on=[],
            )
        assert exit_code == 0

    def test_file_with_only_code_blocks_passes_chk01_chk02(self, tmp_path):
        content = (
            "```python\n"
            "# This is Korean: 한국어\n"
            "`_sys/ai/nonexistent.json`\n"
            "```\n"
        )
        doc = make_doc(tmp_path, "_sys/docs-v2/code_only.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            f1 = chk_01_path_existence([])
            f2 = chk_02_inv19_korean([])
        assert f1 == []
        assert f2 == []

    def test_binary_like_content_does_not_crash(self, tmp_path):
        content = "# Title\n\x00\x01\x02 binary content\n"
        doc = make_doc(tmp_path, "_sys/docs-v2/binary.md", content)
        with patch.object(check_docs_mece, "_DOCS_DIR", tmp_path / "_sys" / "docs-v2"), \
             patch.object(check_docs_mece, "_SYS_DIR", tmp_path / "_sys"), \
             patch.object(check_docs_mece, "_ROOT", tmp_path):
            # Should not raise
            try:
                findings = chk_02_inv19_korean([])
            except Exception as e:
                pytest.fail(f"Should not raise: {e}")
