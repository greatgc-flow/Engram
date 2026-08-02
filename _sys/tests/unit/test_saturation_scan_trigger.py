"""Regression test for T89: saturation_scan.py's commit-interval trigger
treated a missing `commit_count` key in state.json the same as a legitimate
commit_count=0, and `0 % 10 == 0` made every run look like an exact multiple
of 10. Since nothing in the codebase ever writes `commit_count`, the scan ran
unconditionally on every self_care invocation instead of every 10th commit.
"""
import json
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent.parent  # _sys/
sys.path.insert(0, str(SYS_DIR / "checks"))
import saturation_scan as sat  # noqa: E402


def test_read_commit_count_returns_none_when_no_state_file(tmp_path):
    sys_root = tmp_path / "_sys"
    sys_root.mkdir()
    assert sat._read_commit_count(sys_root) is None


def test_read_commit_count_returns_none_when_key_missing(tmp_path):
    sys_root = tmp_path / "_sys"
    sys_root.mkdir()
    ai_state = tmp_path / ".ai" / "state.json"
    ai_state.parent.mkdir(parents=True)
    ai_state.write_text(json.dumps({"leader": "cc"}), encoding="utf-8")

    assert sat._read_commit_count(sys_root) is None


def test_read_commit_count_returns_value_when_key_present(tmp_path):
    sys_root = tmp_path / "_sys"
    sys_root.mkdir()
    ai_state = tmp_path / ".ai" / "state.json"
    ai_state.parent.mkdir(parents=True)
    ai_state.write_text(json.dumps({"commit_count": 20}), encoding="utf-8")

    assert sat._read_commit_count(sys_root) == 20


def test_main_skips_when_commit_count_untracked(tmp_path, capsys):
    sys_root = tmp_path / "_sys"
    sys_root.mkdir()

    from unittest.mock import patch

    with patch.object(sys, "argv", ["saturation_scan.py", "--sys-root", str(sys_root)]):
        try:
            sat.main()
        except SystemExit as e:
            assert e.code == 0
    out = capsys.readouterr().out
    assert "[SKIP]" in out
    assert "not tracked" in out


def test_main_runs_when_forced_despite_untracked_commit_count(tmp_path, capsys):
    sys_root = tmp_path / "_sys"
    sys_root.mkdir()

    from unittest.mock import patch

    with patch.object(sys, "argv", ["saturation_scan.py", "--sys-root", str(sys_root), "--force"]):
        try:
            sat.main()
        except SystemExit as e:
            assert e.code in (0, 1)
    out = capsys.readouterr().out
    assert "[START]" in out
    assert "commit_count=untracked" in out


def test_main_skips_explicit_zero_commit_count(tmp_path, capsys):
    """T89(c) groups commit_count=0 with 'missing' -- an explicit 0 must not
    be treated as a valid every-10th-commit trigger either, since nothing
    writes this key yet and 0 % 10 == 0 would otherwise fire every time."""
    sys_root = tmp_path / "_sys"
    sys_root.mkdir()
    ai_state = tmp_path / ".ai" / "state.json"
    ai_state.parent.mkdir(parents=True)
    ai_state.write_text(json.dumps({"commit_count": 0}), encoding="utf-8")

    from unittest.mock import patch

    with patch.object(sys, "argv", ["saturation_scan.py", "--sys-root", str(sys_root)]):
        try:
            sat.main()
        except SystemExit as e:
            assert e.code == 0
    out = capsys.readouterr().out
    assert "[SKIP] commit_count=0" in out


def test_main_runs_when_forced_despite_explicit_zero_commit_count(tmp_path, capsys):
    sys_root = tmp_path / "_sys"
    sys_root.mkdir()
    ai_state = tmp_path / ".ai" / "state.json"
    ai_state.parent.mkdir(parents=True)
    ai_state.write_text(json.dumps({"commit_count": 0}), encoding="utf-8")

    from unittest.mock import patch

    with patch.object(sys, "argv", ["saturation_scan.py", "--sys-root", str(sys_root), "--force"]):
        try:
            sat.main()
        except SystemExit as e:
            assert e.code in (0, 1)
    out = capsys.readouterr().out
    assert "[START]" in out
    assert "commit_count=0" in out


def test_main_still_skips_non_multiple_when_count_present(tmp_path, capsys):
    sys_root = tmp_path / "_sys"
    sys_root.mkdir()
    ai_state = tmp_path / ".ai" / "state.json"
    ai_state.parent.mkdir(parents=True)
    ai_state.write_text(json.dumps({"commit_count": 7}), encoding="utf-8")

    from unittest.mock import patch

    with patch.object(sys, "argv", ["saturation_scan.py", "--sys-root", str(sys_root)]):
        try:
            sat.main()
        except SystemExit as e:
            assert e.code == 0
    out = capsys.readouterr().out
    assert "[SKIP] commit_count=7" in out
