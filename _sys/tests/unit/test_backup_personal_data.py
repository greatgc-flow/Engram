"""Tests for backup_personal_data.py (item 11, dotdir consolidation,
ratified 2026-09-09): backup/restore of the 3 AI CLIs' durable data,
sourced from the single `.engram/` live root."""

import shutil
import sys
import zipfile
from pathlib import Path

import pytest

SYS = Path(__file__).resolve().parents[2]
CHECKS_DIR = SYS / "checks"
if str(CHECKS_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKS_DIR))

from backup_personal_data import (  # noqa: E402
    CREDENTIAL_SHAPED_NAMES,
    check_running_processes,
    do_backup,
    do_list,
    do_reset,
    do_restore,
    main,
    run_backup,
    run_reset,
    run_restore,
)



def _seed_engram(engram_dir: Path) -> None:
    (engram_dir / "claude").mkdir(parents=True)
    (engram_dir / "claude" / "CLAUDE.md").write_text("claude memory", encoding="utf-8")
    (engram_dir / "claude" / "settings.json").write_text("{}", encoding="utf-8")
    (engram_dir / "claude" / "projects").mkdir()
    (engram_dir / "claude" / "projects" / "session-1.jsonl").write_text("{}", encoding="utf-8")

    (engram_dir / "codex").mkdir(parents=True)
    (engram_dir / "codex" / "CODEX.md").write_text("codex memory", encoding="utf-8")
    (engram_dir / "codex" / "config.toml").write_text("[x]\n", encoding="utf-8")


def test_backup_bundles_present_items_and_writes_manifest(tmp_path: Path) -> None:
    engram_dir = tmp_path / ".engram"
    _seed_engram(engram_dir)
    out_dir = tmp_path / "bundle"

    result = do_backup(engram_dir, out_dir)

    assert result == out_dir
    assert (out_dir / "claude" / "CLAUDE.md").read_text(encoding="utf-8") == "claude memory"
    assert (out_dir / "claude" / "projects" / "session-1.jsonl").is_file()
    assert (out_dir / "codex" / "CODEX.md").read_text(encoding="utf-8") == "codex memory"
    manifest = (out_dir / "MANIFEST.txt").read_text(encoding="utf-8")
    assert "claude/CLAUDE.md" in manifest
    assert "SKIPPED" in manifest  # agy/* was never seeded


def test_backup_skips_absent_items_without_error(tmp_path: Path) -> None:
    engram_dir = tmp_path / ".engram"
    engram_dir.mkdir()  # completely empty -- no tool has run yet
    out_dir = tmp_path / "bundle"

    do_backup(engram_dir, out_dir)

    assert (out_dir / "MANIFEST.txt").is_file()
    assert not (out_dir / "claude").exists()


def test_backup_bundle_never_contains_credential_shaped_files(tmp_path: Path) -> None:
    """Item 11's release scenario: a fixture .engram/ containing auth.json,
    hosts.yml and cache/ must produce a bundle containing none of them --
    not via active filtering, but because ITEMS never names them."""

    engram_dir = tmp_path / ".engram"
    _seed_engram(engram_dir)
    (engram_dir / "codex" / "auth.json").write_text("SECRET-TOKEN", encoding="utf-8")
    (engram_dir / "gh").mkdir(parents=True)
    (engram_dir / "gh" / "hosts.yml").write_text("SECRET-HOST", encoding="utf-8")
    (engram_dir / "claude" / "cache").mkdir(parents=True)
    (engram_dir / "claude" / "cache" / "blob.bin").write_text("cache bytes", encoding="utf-8")

    out_dir = tmp_path / "bundle"
    do_backup(engram_dir, out_dir)

    bundled_names = {p.name.lower() for p in out_dir.rglob("*") if p.is_file()}
    assert not (bundled_names & CREDENTIAL_SHAPED_NAMES)
    assert not (out_dir / "gh").exists()
    assert not (out_dir / "claude" / "cache").exists()
    # The real, allowlisted sibling content is still captured.
    assert (out_dir / "codex" / "CODEX.md").is_file()


def test_backup_overwrites_stale_bundle_content_on_rerun(tmp_path: Path) -> None:
    engram_dir = tmp_path / ".engram"
    _seed_engram(engram_dir)
    out_dir = tmp_path / "bundle"
    do_backup(engram_dir, out_dir)

    (engram_dir / "claude" / "CLAUDE.md").write_text("updated memory", encoding="utf-8")
    do_backup(engram_dir, out_dir)

    assert (out_dir / "claude" / "CLAUDE.md").read_text(encoding="utf-8") == "updated memory"


def test_restore_copies_bundle_back_into_engram(tmp_path: Path) -> None:
    source_engram = tmp_path / "source" / ".engram"
    _seed_engram(source_engram)
    bundle_dir = tmp_path / "bundle"
    do_backup(source_engram, bundle_dir)

    target_engram = tmp_path / "target" / ".engram"
    do_restore(target_engram, bundle_dir, force=False)

    assert (target_engram / "claude" / "CLAUDE.md").read_text(encoding="utf-8") == "claude memory"
    assert (target_engram / "codex" / "config.toml").is_file()


def test_restore_refuses_to_overwrite_existing_projects_without_force(tmp_path: Path) -> None:
    source_engram = tmp_path / "source" / ".engram"
    _seed_engram(source_engram)
    bundle_dir = tmp_path / "bundle"
    do_backup(source_engram, bundle_dir)

    target_engram = tmp_path / "target" / ".engram"
    (target_engram / "claude" / "projects").mkdir(parents=True)
    (target_engram / "claude" / "projects" / "existing-session.jsonl").write_text(
        "irreplaceable", encoding="utf-8"
    )

    do_restore(target_engram, bundle_dir, force=False)

    # Refused: the existing live session data is untouched.
    assert (target_engram / "claude" / "projects" / "existing-session.jsonl").is_file()
    assert not (target_engram / "claude" / "projects" / "session-1.jsonl").exists()


def test_restore_overwrites_projects_when_forced(tmp_path: Path) -> None:
    source_engram = tmp_path / "source" / ".engram"
    _seed_engram(source_engram)
    bundle_dir = tmp_path / "bundle"
    do_backup(source_engram, bundle_dir)

    target_engram = tmp_path / "target" / ".engram"
    (target_engram / "claude" / "projects").mkdir(parents=True)
    (target_engram / "claude" / "projects" / "existing-session.jsonl").write_text(
        "old", encoding="utf-8"
    )

    do_restore(target_engram, bundle_dir, force=True)

    assert (target_engram / "claude" / "projects" / "session-1.jsonl").is_file()
    assert not (target_engram / "claude" / "projects" / "existing-session.jsonl").exists()


def test_list_prints_manifest_when_present(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    engram_dir = tmp_path / ".engram"
    _seed_engram(engram_dir)
    bundle_dir = tmp_path / "bundle"
    do_backup(engram_dir, bundle_dir)
    capsys.readouterr()

    do_list(bundle_dir)

    output = capsys.readouterr().out
    assert "backup_personal_data.py .engram/ backup bundle" in output


def test_list_falls_back_to_directory_listing_without_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "codex").mkdir()

    do_list(bundle_dir)

    output = capsys.readouterr().out
    assert "no MANIFEST.txt found" in output
    assert "codex/" in output


def test_main_backup_then_restore_round_trip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base_dir = tmp_path / "base"
    _seed_engram(base_dir / ".engram")
    out_dir = tmp_path / "bundle"

    assert main(["--base-dir", str(base_dir), "--backup", "--out", str(out_dir)]) == 0
    assert (out_dir / "MANIFEST.txt").is_file()

    other_base = tmp_path / "other-base"
    assert main(["--base-dir", str(other_base), "--restore", str(out_dir)]) == 0
    assert (other_base / ".engram" / "claude" / "CLAUDE.md").is_file()


def test_main_backup_without_out_errors(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["--base-dir", str(tmp_path), "--backup"])


def test_main_list_does_not_require_base_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    engram_dir = tmp_path / "base" / ".engram"
    _seed_engram(engram_dir)
    out_dir = tmp_path / "bundle"
    do_backup(engram_dir, out_dir)

    assert main(["--list", str(out_dir)]) == 0


def test_backup_zip_default_destination_and_disaster_recovery_notice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base_dir = tmp_path / "engram_base"
    engram_dir = base_dir / ".engram"
    _seed_engram(engram_dir)
    capsys.readouterr()

    result = do_backup(engram_dir, base_dir=base_dir)

    assert result.is_file()
    assert result.suffix == ".zip"
    assert result.parent == base_dir / "_sys" / "data" / "backups"
    assert result.name.startswith("engram_backup_")
    assert zipfile.is_zipfile(result)

    with zipfile.ZipFile(result, "r") as zf:
        names = zf.namelist()
        assert "MANIFEST.txt" in names
        assert "claude/CLAUDE.md" in names
        assert "claude/projects/session-1.jsonl" in names
        assert "codex/CODEX.md" in names
        assert "codex/config.toml" in names
        manifest_text = zf.read("MANIFEST.txt").decode("utf-8")
        assert "claude/CLAUDE.md" in manifest_text
        assert "SKIPPED" in manifest_text

    stdout = capsys.readouterr().out
    assert "[NOTE] Same-drive backup created." in stdout
    assert "NOT drive failure." in stdout


def test_backup_custom_out_zip_and_directory(tmp_path: Path) -> None:
    engram_dir = tmp_path / ".engram"
    _seed_engram(engram_dir)

    # 1. Custom zip file path
    custom_zip = tmp_path / "custom" / "my_backup.zip"
    res1 = do_backup(engram_dir, custom_zip, as_zip=True)
    assert res1 == custom_zip
    assert zipfile.is_zipfile(res1)

    # 2. Existing directory
    custom_dir = tmp_path / "archive_dir"
    custom_dir.mkdir()
    res2 = do_backup(engram_dir, custom_dir, as_zip=True)
    assert res2.parent == custom_dir
    assert res2.name.startswith("engram_backup_")
    assert res2.suffix == ".zip"
    assert zipfile.is_zipfile(res2)

    # 3. Path ending in slash treated as directory
    custom_dir2 = tmp_path / "archive_dir2"
    res3 = do_backup(engram_dir, str(custom_dir2) + "/", as_zip=True)
    assert res3.parent == custom_dir2
    assert res3.name.startswith("engram_backup_")
    assert zipfile.is_zipfile(res3)

    # 4. Custom file path without .zip extension
    no_ext = tmp_path / "backup_archive"
    res4 = do_backup(engram_dir, no_ext, as_zip=True)
    assert res4 == tmp_path / "backup_archive.zip"
    assert zipfile.is_zipfile(res4)


def test_backup_emits_warning_when_process_is_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    engram_dir = tmp_path / ".engram"
    _seed_engram(engram_dir)
    out_zip = tmp_path / "backup.zip"

    monkeypatch.setattr(
        "backup_personal_data.check_running_processes",
        lambda sys_dir: ["claude.exe", "codex.exe"],
    )
    capsys.readouterr()

    res = do_backup(engram_dir, out_zip, as_zip=True)

    assert res == out_zip
    assert zipfile.is_zipfile(res)
    stdout = capsys.readouterr().out
    assert "[WARNING] Managed AI process(es) currently running: claude.exe, codex.exe" in stdout
    assert "partial reads" in stdout


def test_restore_from_zip_archive(tmp_path: Path) -> None:
    source_engram = tmp_path / "source" / ".engram"
    _seed_engram(source_engram)
    out_zip = tmp_path / "bundle.zip"
    do_backup(source_engram, out_zip, as_zip=True)

    target_engram = tmp_path / "target" / ".engram"
    do_restore(target_engram, out_zip, force=False)

    assert (target_engram / "claude" / "CLAUDE.md").read_text(encoding="utf-8") == "claude memory"
    assert (target_engram / "claude" / "projects" / "session-1.jsonl").is_file()
    assert (target_engram / "codex" / "CODEX.md").read_text(encoding="utf-8") == "codex memory"
    assert (target_engram / "codex" / "config.toml").is_file()


def test_restore_refuses_when_process_is_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source_engram = tmp_path / "source" / ".engram"
    _seed_engram(source_engram)
    out_zip = tmp_path / "bundle.zip"
    do_backup(source_engram, out_zip, as_zip=True)

    target_engram = tmp_path / "target" / ".engram"
    target_engram.mkdir(parents=True)
    (target_engram / "untouched.txt").write_text("initial", encoding="utf-8")

    monkeypatch.setattr(
        "backup_personal_data.check_running_processes",
        lambda sys_dir: ["claude.exe"],
    )
    capsys.readouterr()

    with pytest.raises(SystemExit) as exc:
        do_restore(target_engram, out_zip)

    assert exc.value.code == 1
    assert (target_engram / "untouched.txt").is_file()
    assert not (target_engram / "claude").exists()
    stdout = capsys.readouterr().out
    assert "[Error] Cannot restore: managed AI CLI process(es) currently running: claude.exe" in stdout
    assert "Please close all running AI CLIs and try again." in stdout


def test_restore_creates_pre_restore_snapshot_when_live_engram_has_content(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    target_engram = base_dir / ".engram"
    target_engram.mkdir(parents=True)
    (target_engram / "claude").mkdir()
    (target_engram / "claude" / "CLAUDE.md").write_text("pre-existing memory", encoding="utf-8")

    source_engram = tmp_path / "source" / ".engram"
    source_engram.mkdir(parents=True)
    (source_engram / "claude").mkdir()
    (source_engram / "claude" / "CLAUDE.md").write_text("incoming new memory", encoding="utf-8")
    source_zip = tmp_path / "source_backup.zip"
    do_backup(source_engram, source_zip, as_zip=True)

    do_restore(target_engram, source_zip, force=False, base_dir=base_dir)

    backups_dir = base_dir / "_sys" / "data" / "backups"
    assert backups_dir.is_dir()
    pre_snapshots = list(backups_dir.glob("pre_restore_*.zip"))
    assert len(pre_snapshots) == 1
    snap = pre_snapshots[0]
    assert zipfile.is_zipfile(snap)

    with zipfile.ZipFile(snap, "r") as zf:
        assert "claude/CLAUDE.md" in zf.namelist()
        assert zf.read("claude/CLAUDE.md").decode("utf-8") == "pre-existing memory"

    assert (target_engram / "claude" / "CLAUDE.md").read_text(encoding="utf-8") == "incoming new memory"


def test_restore_force_skips_pre_restore_snapshot(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    target_engram = base_dir / ".engram"
    target_engram.mkdir(parents=True)
    (target_engram / "claude").mkdir()
    (target_engram / "claude" / "CLAUDE.md").write_text("pre-existing memory", encoding="utf-8")

    source_engram = tmp_path / "source" / ".engram"
    source_engram.mkdir(parents=True)
    (source_engram / "claude").mkdir()
    (source_engram / "claude" / "CLAUDE.md").write_text("incoming new memory", encoding="utf-8")
    source_zip = tmp_path / "source_backup.zip"
    do_backup(source_engram, source_zip, as_zip=True)

    do_restore(target_engram, source_zip, force=True, base_dir=base_dir)

    backups_dir = base_dir / "_sys" / "data" / "backups"
    if backups_dir.exists():
        assert len(list(backups_dir.glob("pre_restore_*.zip"))) == 0


def test_restore_empty_or_absent_engram_skips_pre_restore_snapshot(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    target_engram = base_dir / ".engram"  # does not exist

    source_engram = tmp_path / "source" / ".engram"
    _seed_engram(source_engram)
    source_zip = tmp_path / "source_backup.zip"
    do_backup(source_engram, source_zip, as_zip=True)

    do_restore(target_engram, source_zip, force=False, base_dir=base_dir)

    backups_dir = base_dir / "_sys" / "data" / "backups"
    if backups_dir.exists():
        assert len(list(backups_dir.glob("pre_restore_*.zip"))) == 0


def test_restore_invalid_target_errors(tmp_path: Path) -> None:
    target_engram = tmp_path / ".engram"

    with pytest.raises(SystemExit) as exc1:
        do_restore(target_engram, tmp_path / "missing.zip")
    assert "Path does not exist" in str(exc1.value)

    bad_file = tmp_path / "not_a_bundle.txt"
    bad_file.write_text("raw text", encoding="utf-8")
    with pytest.raises(SystemExit) as exc2:
        do_restore(target_engram, bad_file)
    assert "Not a valid zip file or directory" in str(exc2.value)


def test_list_with_zip_archive_and_fallbacks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    engram_dir = tmp_path / ".engram"
    _seed_engram(engram_dir)
    zip_path = tmp_path / "bundle.zip"
    do_backup(engram_dir, zip_path, as_zip=True)
    capsys.readouterr()

    # 1. Zip with MANIFEST.txt
    do_list(zip_path)
    output = capsys.readouterr().out
    assert "backup_personal_data.py .engram/ backup bundle" in output

    # 2. Zip without MANIFEST.txt
    zip_no_manifest = tmp_path / "no_manifest.zip"
    with zipfile.ZipFile(zip_no_manifest, "w") as zf:
        zf.writestr("claude/CLAUDE.md", "claude data")
        zf.writestr("codex/CODEX.md", "codex data")
    do_list(zip_no_manifest)
    output2 = capsys.readouterr().out
    assert "no MANIFEST.txt found" in output2
    assert "claude" in output2
    assert "codex" in output2

    # 3. Missing path
    with pytest.raises(SystemExit) as exc1:
        do_list(tmp_path / "missing_file")
    assert "Path does not exist" in str(exc1.value)

    # 4. Not a zip and not a dir
    bad_file = tmp_path / "bad.bin"
    bad_file.write_bytes(b"\x00\x01\x02")
    with pytest.raises(SystemExit) as exc2:
        do_list(bad_file)
    assert "Not a valid zip file or directory" in str(exc2.value)


def test_reset_cancelled_by_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base_dir = tmp_path / "base"
    engram_dir = base_dir / ".engram"
    _seed_engram(engram_dir)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    capsys.readouterr()

    with pytest.raises(SystemExit) as exc:
        do_reset(base_dir, yes=False)

    assert exc.value.code == 3
    assert engram_dir.exists()
    assert (engram_dir / "claude" / "CLAUDE.md").is_file()
    assert "Reset cancelled." in capsys.readouterr().out


def test_reset_default_scope_deletes_engram_leaves_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_dir = tmp_path / "base"
    engram_dir = base_dir / ".engram"
    _seed_engram(engram_dir)
    workspace = base_dir / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "my_project.py").write_text("print('hello')", encoding="utf-8")

    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    do_reset(base_dir, yes=False)

    assert not engram_dir.exists()
    assert workspace.exists()
    assert (workspace / "my_project.py").read_text(encoding="utf-8") == "print('hello')"


def test_reset_yes_flag_bypasses_confirmation(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    engram_dir = base_dir / ".engram"
    _seed_engram(engram_dir)
    workspace = base_dir / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "project.py").write_text("code", encoding="utf-8")

    do_reset(base_dir, yes=True)

    assert not engram_dir.exists()
    assert workspace.exists()


def test_reset_all_scope_aborts_on_name_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base_dir = tmp_path / "target_root"
    engram_dir = base_dir / ".engram"
    _seed_engram(engram_dir)
    workspace = base_dir / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "important.py").write_text("keep", encoding="utf-8")

    monkeypatch.setattr("builtins.input", lambda prompt: "wrong_root_name")
    capsys.readouterr()

    with pytest.raises(SystemExit) as exc:
        do_reset(base_dir, yes=True, all_data=True)

    assert exc.value.code == 3
    assert engram_dir.exists()
    assert workspace.exists()
    assert (workspace / "important.py").is_file()
    assert "Folder name does not match. Aborting." in capsys.readouterr().out


def test_reset_all_scope_deletes_both_on_name_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_dir = tmp_path / "target_root"
    engram_dir = base_dir / ".engram"
    _seed_engram(engram_dir)
    workspace = base_dir / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "important.py").write_text("code", encoding="utf-8")

    monkeypatch.setattr("builtins.input", lambda prompt: "target_root")
    do_reset(base_dir, yes=True, all_data=True)

    assert not engram_dir.exists()
    assert not workspace.exists()


def test_reset_refuses_when_process_is_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base_dir = tmp_path / "base"
    engram_dir = base_dir / ".engram"
    _seed_engram(engram_dir)

    monkeypatch.setattr(
        "backup_personal_data.check_running_processes",
        lambda sys_dir: ["agy.exe"],
    )
    capsys.readouterr()

    with pytest.raises(SystemExit) as exc:
        do_reset(base_dir, yes=True)

    assert exc.value.code == 1
    assert engram_dir.exists()
    stdout = capsys.readouterr().out
    assert "[Error] Cannot reset: managed AI CLI process(es) currently running: agy.exe" in stdout
    assert "Please close all running AI CLIs and try again." in stdout


def test_reset_handles_input_interrupts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base_dir = tmp_path / "base"
    engram_dir = base_dir / ".engram"
    _seed_engram(engram_dir)

    def raise_interrupt(_prompt: str) -> str:
        raise KeyboardInterrupt()

    monkeypatch.setattr("builtins.input", raise_interrupt)
    with pytest.raises(SystemExit) as exc1:
        do_reset(base_dir, yes=False)
    assert exc1.value.code == 3

    def raise_eof(_prompt: str) -> str:
        raise EOFError()

    monkeypatch.setattr("builtins.input", raise_eof)
    with pytest.raises(SystemExit) as exc2:
        do_reset(base_dir, yes=True, all_data=True)
    assert exc2.value.code == 3


def test_check_running_processes_with_lease_mock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_is_peer_leased(sys_dir: Path, tool: str) -> bool:
        return tool == "claude"

    import core.provisioner
    monkeypatch.setattr(core.provisioner, "_is_peer_leased", fake_is_peer_leased)

    running = check_running_processes(tmp_path)
    assert running == ["claude.exe"]


def test_run_backup_dispatcher_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_dir = tmp_path / "base"
    engram_dir = base_dir / ".engram"
    _seed_engram(engram_dir)
    sys_dir = base_dir / "_sys"

    # 1. Explicit out path
    custom_zip = tmp_path / "out" / "backup.zip"
    ctx1 = {"base_dir": base_dir, "sys_dir": sys_dir, "args": ["--out", str(custom_zip)]}
    run_backup(ctx1)
    assert custom_zip.is_file()
    assert zipfile.is_zipfile(custom_zip)

    # 2. Relative out path with ENGRAM_CALLER_CWD
    caller_dir = tmp_path / "caller_cwd"
    caller_dir.mkdir()
    monkeypatch.setenv("ENGRAM_CALLER_CWD", str(caller_dir))
    ctx2 = {"base_dir": base_dir, "sys_dir": sys_dir, "args": ["--out", "rel_backup.zip"]}
    run_backup(ctx2)
    assert (caller_dir / "rel_backup.zip").is_file()

    # 3. Default path (no args)
    ctx3 = {"base_dir": base_dir, "sys_dir": sys_dir, "args": []}
    run_backup(ctx3)
    backups = list((sys_dir / "data" / "backups").glob("engram_backup_*.zip"))
    assert len(backups) >= 1

    # 4. Error if --out given without PATH
    ctx4 = {"base_dir": base_dir, "sys_dir": sys_dir, "args": ["--out"]}
    with pytest.raises(SystemExit) as exc:
        run_backup(ctx4)
    assert exc.value.code == 2


def test_run_restore_dispatcher_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_base = tmp_path / "src_base"
    _seed_engram(source_base / ".engram")
    backup_zip = tmp_path / "source.zip"
    do_backup(source_base / ".engram", backup_zip, as_zip=True)

    # 1. Standard restore with absolute path
    target_base = tmp_path / "dst_base"
    ctx1 = {
        "base_dir": target_base,
        "sys_dir": target_base / "_sys",
        "args": [str(backup_zip), "--force"],
    }
    run_restore(ctx1)
    assert (target_base / ".engram" / "claude" / "CLAUDE.md").is_file()

    # 2. Relative restore with ENGRAM_CALLER_CWD
    caller_dir = tmp_path / "caller"
    caller_dir.mkdir()
    shutil.copy2(backup_zip, caller_dir / "rel.zip")
    monkeypatch.setenv("ENGRAM_CALLER_CWD", str(caller_dir))
    target_base2 = tmp_path / "dst_base2"
    ctx2 = {
        "base_dir": target_base2,
        "sys_dir": target_base2 / "_sys",
        "args": ["rel.zip", "--force"],
    }
    run_restore(ctx2)
    assert (target_base2 / ".engram" / "claude" / "CLAUDE.md").is_file()

    # 3. Missing path argument
    ctx3 = {
        "base_dir": target_base,
        "sys_dir": target_base / "_sys",
        "args": ["--force"],
    }
    with pytest.raises(SystemExit) as exc:
        run_restore(ctx3)
    assert exc.value.code == 2


def test_run_reset_dispatcher_adapter(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    _seed_engram(base_dir / ".engram")
    workspace = base_dir / "workspace"
    workspace.mkdir()
    (workspace / "project.py").write_text("code", encoding="utf-8")

    ctx = {
        "base_dir": base_dir,
        "sys_dir": base_dir / "_sys",
        "args": ["--yes"],
    }
    run_reset(ctx)
    assert not (base_dir / ".engram").exists()
    assert workspace.exists()


def test_main_reset_and_zip_restore_round_trip(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    _seed_engram(base_dir / ".engram")
    out_zip = tmp_path / "bundle.zip"

    # Backup to zip via main
    assert main(["--base-dir", str(base_dir), "--backup", "--out", str(out_zip)]) == 0
    assert zipfile.is_zipfile(out_zip)

    # Restore from zip via main
    other_base = tmp_path / "other"
    assert main(["--base-dir", str(other_base), "--restore", str(out_zip)]) == 0
    assert (other_base / ".engram" / "claude" / "CLAUDE.md").is_file()

    # Reset via main
    assert main(["--base-dir", str(other_base), "--reset", "--yes"]) == 0
    assert not (other_base / ".engram").exists()

