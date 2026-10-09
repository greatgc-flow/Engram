"""Fault real CLI bodies against docs/cli_reference.md and CORE_INVARIANTS.

Body faults must fail explicitly without a success message. Default restore and
reset preserve covered personal data in a printed safety snapshot; tidy removes
regenerable debris. None promises journaled undo for these bodies. --force restore
waives the snapshot, and standard backup excludes credentials/uncovered bytes.
"""

import json
import shutil
from pathlib import Path

import pytest

from core import dispatcher, tidy_temp
import zipfile
from checks import backup_personal_data


@pytest.fixture
def cli_root(tmp_path, monkeypatch):
    root = tmp_path / "Engram fault fixture"
    sys_dir = root / "_sys"
    (sys_dir / "config").mkdir(parents=True)
    (sys_dir / "config" / "environment.json").write_text(
        json.dumps({"paths": {"state": str(sys_dir / "data" / "state")}}),
        encoding="utf-8",
    )
    shutil.copy2(Path(dispatcher.__file__).parents[1] / "dispatch.json",
                 sys_dir / "dispatch.json")
    monkeypatch.setattr(dispatcher, "base_dir", root)
    monkeypatch.setattr(dispatcher, "sys_dir", sys_dir)
    # Preserve tidy's module globals because run() configures them in place.
    for name, value in vars(tidy_temp).copy().items():
        if name.isupper():
            monkeypatch.setattr(tidy_temp, name, value)
    monkeypatch.setattr(backup_personal_data, "check_running_processes", lambda _: [])
    return root, sys_dir


def _tree(path):
    return {p.relative_to(path).as_posix(): p.read_bytes()
            for p in path.rglob("*") if p.is_file()} if path.exists() else {}


def _invoke(verb, *args):
    """Match script exit semantics while leaving unexpected exceptions visible."""
    try:
        return dispatcher.main(["dispatcher.py", verb, *map(str, args)])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    except (OSError, RuntimeError):
        return 1


@pytest.mark.parametrize("verb", ["tidy", "restore", "reset"])
def test_public_cli_body_failure_reports_error_and_preserves_recovery(
        cli_root, monkeypatch, capsys, verb):
    root, sys_dir = cli_root
    if verb == "tidy":
        target = sys_dir / "tests" / ".pytest_cache"
        args = ["--only", "pytest_cache_default", "--apply"]
    else:
        target = root / ".engram"
        args = ["--apply", "--yes"] if verb == "reset" else []
    original_file = target / "claude" / "settings.json"
    original_file.parent.mkdir(parents=True)
    original_file.write_bytes(b'{"original":true}')
    (target / "untouched.bin").write_bytes(b"preserve non-allowlisted data too")
    before = _tree(target)
    if verb == "restore":
        bundle = root / "restore-bundle"
        incoming = bundle / "claude" / "settings.json"
        incoming.parent.mkdir(parents=True)
        incoming.write_bytes(b'{"replacement":true}')
        args = [bundle, "--apply"]  # --force explicitly waives snapshot recovery

    observed = {"mutation": 0}
    real_copy2, real_rmtree, real_unlink = shutil.copy2, shutil.rmtree, Path.unlink

    def copy2(src, dst, *a, **kw):
        result = real_copy2(src, dst, *a, **kw)
        if verb == "restore" and not observed["mutation"] and Path(dst) == original_file:
            assert original_file.read_bytes() != before["claude/settings.json"]
            observed["mutation"] += 1
            raise OSError("injected mutation body fault after filesystem write")
        return result

    def rmtree(path, *a, **kw):
        path = Path(path)
        is_victim = (path == target or
                     (verb == "reset" and path.name.endswith("_.engram")))
        if verb != "restore" and is_victim and not observed["mutation"]:
            # Delete one real file while retaining other data: failure must
            # handle a partially executed body, not just a rejected preflight.
            victim = next(p for p in path.rglob("*") if p.is_file())
            victim.unlink()
            observed["mutation"] += 1
            raise OSError("injected mutation body fault after filesystem deletion")
        return real_rmtree(path, *a, **kw)

    def unlink(path, *a, **kw):
        result = real_unlink(path, *a, **kw)
        if verb == "reset" and path == original_file and not observed["mutation"]:
            observed["mutation"] += 1
            raise OSError("injected mutation body fault after filesystem deletion")
        return result

    monkeypatch.setattr(Path, "unlink", unlink)
    monkeypatch.setattr(shutil, "copy2", copy2)
    monkeypatch.setattr(shutil, "rmtree", rmtree)
    code = _invoke(verb, *args)
    output = capsys.readouterr().out
    assert observed["mutation"] == 1, "fault must run inside the real mutation body"
    assert code != 0, output
    assert "[Error]" in output and "injected mutation body fault" in output
    # Snapshot backups print "Done. Manifest ..." before the mutation body.
    # Match the operation's complete success line so false success still fails.
    if verb in ("restore", "reset"):
        success_line = "Done." if verb == "restore" else "Reset complete."
        assert success_line not in output.splitlines(), output
    assert "(applied)" not in output
    if verb == "tidy":
        # cli_reference: caches are regenerable debris, with no undo guarantee.
        # EN-INV-015 protects recovery material, not disposable cache bytes.
        assert not (root / ".engram").exists()
        return

    # Reset EN-INV-008/009 and default restore promise snapshot recovery,
    # not a journal, automatic undo, or preservation of non-backup payloads.
    pattern = "safety_pre_reset_*.zip" if verb == "reset" else "pre_restore_*.zip"
    snapshots = list((sys_dir / "data" / "backups").glob(pattern))
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert str(snapshot) in output, "recovery snapshot path must be printed"
    with zipfile.ZipFile(snapshot) as archive:
        assert archive.testzip() is None
        assert archive.read("claude/settings.json") == before["claude/settings.json"]
    # Exercise the documented recovery command using the real snapshot.
    assert _invoke("restore", snapshot, "--apply") == 0
    assert original_file.read_bytes() == before["claude/settings.json"]
