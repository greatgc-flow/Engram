"""Special-character and Unicode path resilience test suite for Engram CLI.

EN-GAP-P1-007 STEP 1 of 2:
Parametrized matrix of install-root and data-dir names covering special characters:
spaces, Korean, &, %, ^, !, (, ), ;, ', =, ,, [, ], +, and leading/embedded dot names
Windows allows on NTFS. Drives the real CLI entrypoint (_invoke style matching
test_cli_fault_injection.py and test_locked_file_share_mode.py) through a full
backup -> restore --apply round-trip.

Invariants asserted:
1. CLI exit code is 0 for both backup and restore --apply.
2. Restored file bytes match the original file bytes bit-for-bit.
3. No path mangling in printed output (unmangled special path strings present,
   no 8.3 short names, no Unicode replacement characters).
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from checks import backup_personal_data
from core import dispatcher, tidy_temp


# Matrix of NTFS-legal directory names testing various shell, encoding, and path traps
SPECIAL_CHAR_CASES: list[tuple[str, str]] = [
    ("spaces", "name with spaces"),
    ("korean", "한글_설치경로_테스트"),
    ("ampersand", "name & ampersand"),
    ("percent", "name % percent"),
    ("caret", "name ^ caret"),
    ("exclamation", "name ! exclamation"),
    ("paren_open", "name ( open"),
    ("paren_close", "name ) close"),
    ("parens_both", "name (parens)"),
    ("semicolon", "name ; semicolon"),
    ("quote_single", "name ' singlequote"),
    ("equal", "name = equal"),
    ("comma", "name , comma"),
    ("bracket_open", "name [ open"),
    ("bracket_close", "name ] close"),
    ("brackets_both", "name [brackets]"),
    ("plus", "name + plus"),
    ("leading_dot", ".leading_dot_dir"),
    ("embedded_dot", "safe.dot.name"),
    ("multi_dot_lead", ".safe.multi.dot"),
    ("combo", "combo [test] & (100% ^ 'val' = 1, + 2) ! 한글 .safe;"),
]


def _invoke(verb: str, *args: object) -> int:
    """Match script exit semantics while leaving unexpected exceptions visible."""
    try:
        return dispatcher.main(["dispatcher.py", verb, *map(str, args)])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    except (OSError, RuntimeError):
        return 1


@pytest.fixture
def setup_cli_env(monkeypatch):
    """Configure real CLI environment for a given root and data_dir."""
    def _configure(root: Path, data_dir: Path) -> tuple[Path, Path]:
        sys_dir = root / "_sys"
        (sys_dir / "config").mkdir(parents=True, exist_ok=True)
        (sys_dir / "config" / "environment.json").write_text(
            json.dumps({"paths": {"state": str(data_dir / "state")}}),
            encoding="utf-8",
        )
        shutil.copy2(
            Path(dispatcher.__file__).parents[1] / "dispatch.json",
            sys_dir / "dispatch.json",
        )
        monkeypatch.setattr(dispatcher, "base_dir", root)
        monkeypatch.setattr(dispatcher, "sys_dir", sys_dir)
        for name, value in vars(tidy_temp).copy().items():
            if name.isupper():
                monkeypatch.setattr(tidy_temp, name, value)
        monkeypatch.setattr(backup_personal_data, "check_running_processes", lambda _: [])
        return root, sys_dir
    return _configure


@pytest.mark.parametrize("target_type", ["install_root", "data_dir"])
@pytest.mark.parametrize("case_id, special_name", SPECIAL_CHAR_CASES)
def test_special_char_paths_backup_restore_round_trip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    setup_cli_env,
    target_type: str,
    case_id: str,
    special_name: str,
) -> None:
    """Execute backup -> restore --apply round-trip with special characters in install-root or data-dir."""
    if target_type == "install_root":
        root = tmp_path / special_name
        data_dir = root / "_sys" / "data"
    else:
        root = tmp_path / "standard_engram_root"
        data_dir = tmp_path / special_name

    root, sys_dir = setup_cli_env(root, data_dir)

    engram_dir = root / ".engram"
    payloads = {
        "claude/settings.json": f'{{"target": "{target_type}", "name": "{special_name}", "ver": 1}}'.encode("utf-8"),
        "claude/CLAUDE.md": f"# Special character test for {special_name}\nData: & % ^ ! ' = , ; +".encode("utf-8"),
        "agy/knowledge/notes.txt": f"Notes for {special_name} in {target_type}".encode("utf-8"),
    }
    for rel, content in payloads.items():
        p = engram_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)

    # 1. Execute Backup
    if target_type == "install_root":
        backup_code = _invoke("backup")
        backup_captured = capsys.readouterr()
        backup_out = backup_captured.out + backup_captured.err

        assert backup_code == 0, f"Backup failed (exit {backup_code}) for install_root '{special_name}':\n{backup_out}"
        backups = list((sys_dir / "data" / "backups").glob("*.zip"))
        assert len(backups) == 1, f"Expected 1 backup archive, found {len(backups)} in {sys_dir / 'data' / 'backups'}"
        backup_archive = backups[0]

        # Verify unmangled paths in backup output
        assert special_name in backup_out, f"Special name '{special_name}' not in backup output:\n{backup_out}"
        assert str(engram_dir) in backup_out, f"engram_dir path not found in backup output:\n{backup_out}"
        assert str(backup_archive) in backup_out, f"backup_archive path not found in backup output:\n{backup_out}"
    else:
        backup_archive = data_dir / "backups" / "bundle.zip"
        backup_archive.parent.mkdir(parents=True, exist_ok=True)
        backup_code = _invoke("backup", "--out", str(backup_archive))
        backup_captured = capsys.readouterr()
        backup_out = backup_captured.out + backup_captured.err

        assert backup_code == 0, f"Backup failed (exit {backup_code}) for data_dir '{special_name}':\n{backup_out}"
        assert backup_archive.is_file(), f"Custom backup archive not created at {backup_archive}"

        # Verify unmangled paths in backup output
        assert special_name in backup_out, f"Special name '{special_name}' not in backup output:\n{backup_out}"
        assert str(backup_archive) in backup_out, f"backup_archive path not found in backup output:\n{backup_out}"

    assert "~1" not in backup_out or "~1" in special_name, f"8.3 short path mangling detected in backup:\n{backup_out}"
    assert "\ufffd" not in backup_out, f"Unicode replacement character detected in backup:\n{backup_out}"

    # 2. Mutate live files to verify restore actually replaces content
    for rel in payloads:
        (engram_dir / rel).write_bytes(b'{"mutated": true, "corrupted": true}')

    # 3. Execute Restore --apply
    restore_code = _invoke("restore", str(backup_archive), "--apply")
    restore_captured = capsys.readouterr()
    restore_out = restore_captured.out + restore_captured.err

    assert restore_code == 0, f"Restore failed (exit {restore_code}) with archive '{backup_archive}':\n{restore_out}"

    # Verify unmangled paths in restore output
    claude_settings = engram_dir / "claude" / "settings.json"
    assert str(claude_settings) in restore_out, f"Restored file path not found in restore output:\n{restore_out}"
    if target_type == "install_root":
        assert special_name in restore_out, f"Special name '{special_name}' not in restore output:\n{restore_out}"
    assert "~1" not in restore_out or "~1" in special_name, f"8.3 short path mangling detected in restore:\n{restore_out}"
    assert "\ufffd" not in restore_out, f"Unicode replacement character detected in restore:\n{restore_out}"

    # 4. Assert restored bytes equal original bytes bit-for-bit
    for rel, original_bytes in payloads.items():
        restored_path = engram_dir / rel
        assert restored_path.is_file(), f"Restored file does not exist: {restored_path}"
        actual_bytes = restored_path.read_bytes()
        assert actual_bytes == original_bytes, (
            f"Restored bytes mismatch for {rel} under {target_type} '{special_name}'. "
            f"Expected {len(original_bytes)} bytes, got {len(actual_bytes)} bytes."
        )
