"""Tests for backup_personal_data.py (item 11, dotdir consolidation,
ratified 2026-09-09): backup/restore of the 3 AI CLIs' durable data,
sourced from the single `.engram/` live root."""

import sys
from pathlib import Path

import pytest

SYS = Path(__file__).resolve().parents[2]
CHECKS_DIR = SYS / "checks"
if str(CHECKS_DIR) not in sys.path:
    sys.path.insert(0, str(CHECKS_DIR))

from backup_personal_data import (  # noqa: E402
    CREDENTIAL_SHAPED_NAMES,
    do_backup,
    do_list,
    do_restore,
    main,
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
