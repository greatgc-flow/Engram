"""Tests for the LL-20260703-005 phantom-write guard + manifest coverage.

The guard hashes governed files (existing) AND scans for unexpected new entries
at the repo root / _sys top-level (phantom out-of-band writes). ag designed this;
the terminal applied it (peers do not write governed files — LL-005).
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

SYS_DIR = Path(__file__).resolve().parents[2]
CORE_DIR = SYS_DIR / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import hub


def test_phantom_scan_excludes_allowlist_and_flags_unexpected(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".ai").mkdir()
    (tmp_path / "_sys").mkdir()
    (tmp_path / "_sys" / "core").mkdir()
    (tmp_path / "_sys" / "docs-v2").mkdir()
    # unexpected
    (tmp_path / "ops").mkdir()
    (tmp_path / "blat_junk.txt").touch()
    (tmp_path / "_sys" / "scratch").mkdir()

    with patch.object(hub, "_REPO_ROOT", tmp_path):
        phantoms = hub._phantom_scan()

    assert "ops" in phantoms
    assert "blat_junk.txt" in phantoms
    assert "_sys/scratch" in phantoms
    assert ".git" not in phantoms
    assert ".ai" not in phantoms
    assert "_sys" not in phantoms
    assert "_sys/docs-v2" not in phantoms


def test_phantom_scan_crash_safe():
    with patch("os.listdir", side_effect=OSError("denied")):
        assert hub._phantom_scan() == set()


def test_phantom_write_detected_and_logged(tmp_path):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()

    def simulate_ask(*_a, **_k):
        (tmp_path / "new_phantom.txt").touch()

    with patch.object(hub, "_REPO_ROOT", tmp_path), \
         patch.object(hub, "_action_ask_inner", side_effect=simulate_ask), \
         patch.object(hub, "_snapshot_governed_hashes", return_value={}), \
         patch.object(hub, "_now", return_value="2026-07-04T00:00:00Z"):
        hub.action_ask("cc", "q", None, 10, ai_root, allow_governed_mutation=False)

    errors = ai_root / "operational_errors.jsonl"
    assert errors.exists()
    rec = json.loads(errors.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert rec["type"] == "PHANTOM_WRITE"
    assert rec["lesson"] == "LL-20260703-005"
    assert "new_phantom.txt" in rec["changed_files"]


def test_no_phantom_no_log(tmp_path):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()

    with patch.object(hub, "_REPO_ROOT", tmp_path), \
         patch.object(hub, "_action_ask_inner", side_effect=lambda *a, **k: None), \
         patch.object(hub, "_snapshot_governed_hashes", return_value={}):
        hub.action_ask("cc", "q", None, 10, ai_root, allow_governed_mutation=False)

    assert not (ai_root / "operational_errors.jsonl").exists()


def test_phantom_check_skipped_when_allowed(tmp_path):
    ai_root = tmp_path / ".ai"
    ai_root.mkdir()

    def simulate_ask(*_a, **_k):
        (tmp_path / "authorized_new.txt").touch()

    with patch.object(hub, "_REPO_ROOT", tmp_path), \
         patch.object(hub, "_action_ask_inner", side_effect=simulate_ask):
        hub.action_ask("cc", "q", None, 10, ai_root, allow_governed_mutation=True,
                        governed_mutation_reason="test: authorized broker execution")

    assert not (ai_root / "operational_errors.jsonl").exists()


def test_governed_files_now_includes_docs_history(tmp_path):
    docs_history = tmp_path / "_sys" / "docs" / "history"
    docs_history.mkdir(parents=True)
    known = docs_history / "a_doc.md"
    known.write_text("x", encoding="utf-8")

    cfg = {"active_constraints": {"governed_file_manifest": {"include": ["_sys/docs"]}}}
    with patch.object(hub, "_REPO_ROOT", tmp_path):
        governed = hub._governed_files(protocol_cfg=cfg)

    assert known.resolve() in governed
