"""Tests for the .ais/ -> .engram/ migration command (item 7, dotdir
consolidation, ratified 2026-09-09)."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SYS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS / "core"))

from migrate_ais_to_engram import (  # noqa: E402
    MigrationRefused,
    apply_migration,
    main,
    plan_migration,
)


def _no_running_peers(sys_dir, tool):
    return False


@patch("migrate_ais_to_engram._is_peer_leased", side_effect=_no_running_peers)
def test_plan_migration_noop_when_ais_absent(_mock, tmp_path: Path) -> None:
    plan = plan_migration(tmp_path, tmp_path / "_sys")
    assert plan["action"] == "noop"


@patch("migrate_ais_to_engram._is_peer_leased", side_effect=_no_running_peers)
def test_plan_migration_refuses_a_snapshot(_mock, tmp_path: Path) -> None:
    ais = tmp_path / ".ais"
    ais.mkdir()
    (ais / "MANIFEST.txt").write_text("backup_personal_data.py .ais/ snapshot\n", encoding="utf-8")

    with pytest.raises(MigrationRefused, match="SNAPSHOT"):
        plan_migration(tmp_path, tmp_path / "_sys")


@patch("migrate_ais_to_engram._is_peer_leased", side_effect=_no_running_peers)
def test_plan_migration_refuses_when_both_have_real_content(_mock, tmp_path: Path) -> None:
    ais = tmp_path / ".ais"
    ais.mkdir()
    (ais / "claude").mkdir()

    engram = tmp_path / ".engram"
    (engram / "codex").mkdir(parents=True)
    (engram / "codex" / "CODEX.md").write_text("real content", encoding="utf-8")

    with pytest.raises(MigrationRefused, match="already have"):
        plan_migration(tmp_path, tmp_path / "_sys")


@patch("migrate_ais_to_engram._is_peer_leased")
def test_plan_migration_refuses_when_a_peer_is_running(mock_leased, tmp_path: Path) -> None:
    ais = tmp_path / ".ais"
    ais.mkdir()
    mock_leased.side_effect = lambda sys_dir, tool: tool == "codex"

    with pytest.raises(MigrationRefused, match="codex"):
        plan_migration(tmp_path, tmp_path / "_sys")


@patch("migrate_ais_to_engram._is_peer_leased", side_effect=_no_running_peers)
def test_plan_migration_move_when_live_root_and_engram_absent(_mock, tmp_path: Path) -> None:
    ais = tmp_path / ".ais"
    (ais / "claude").mkdir(parents=True)
    (ais / "claude" / "CLAUDE.md").write_text("hi", encoding="utf-8")

    plan = plan_migration(tmp_path, tmp_path / "_sys")

    assert plan["action"] == "move"
    assert plan["source"] == ais
    assert plan["destination"] == tmp_path / ".engram"
    assert plan["credential_shaped_files"] == []


@patch("migrate_ais_to_engram._is_peer_leased", side_effect=_no_running_peers)
def test_plan_migration_reports_credential_shaped_files(_mock, tmp_path: Path) -> None:
    ais = tmp_path / ".ais"
    (ais / "codex").mkdir(parents=True)
    (ais / "codex" / "auth.json").write_text("{}", encoding="utf-8")

    plan = plan_migration(tmp_path, tmp_path / "_sys")

    assert plan["action"] == "move"
    assert len(plan["credential_shaped_files"]) == 1
    assert "auth.json" in plan["credential_shaped_files"][0]


@patch("migrate_ais_to_engram._is_peer_leased", side_effect=_no_running_peers)
def test_apply_migration_moves_not_copies(_mock, tmp_path: Path) -> None:
    ais = tmp_path / ".ais"
    (ais / "claude").mkdir(parents=True)
    (ais / "claude" / "CLAUDE.md").write_text("hi", encoding="utf-8")
    (tmp_path / "ais-env.bat").write_text("set X=1\n", encoding="utf-8")

    plan = plan_migration(tmp_path, tmp_path / "_sys")
    apply_migration(plan)

    assert not ais.exists()
    engram = tmp_path / ".engram"
    assert (engram / "claude" / "CLAUDE.md").read_text(encoding="utf-8") == "hi"
    assert not (tmp_path / "ais-env.bat").exists()


@patch("migrate_ais_to_engram._is_peer_leased", side_effect=_no_running_peers)
def test_apply_migration_onto_an_empty_idempotently_created_engram_dir(
    _mock, tmp_path: Path
) -> None:
    """build_env() (item 6) creates .engram/{claude,codex,agy,gh}/ and
    .engram/peerhub/config/ idempotently on every launch -- an empty
    .engram/ from that must not block a real move."""
    ais = tmp_path / ".ais"
    (ais / "claude").mkdir(parents=True)
    (ais / "claude" / "CLAUDE.md").write_text("hi", encoding="utf-8")

    engram = tmp_path / ".engram"
    (engram / "claude").mkdir(parents=True)  # empty, as build_env() leaves it

    plan = plan_migration(tmp_path, tmp_path / "_sys")
    apply_migration(plan)

    assert (engram / "claude" / "CLAUDE.md").read_text(encoding="utf-8") == "hi"


@patch("migrate_ais_to_engram._is_peer_leased", side_effect=_no_running_peers)
def test_main_dry_run_mutates_nothing(_mock, tmp_path: Path, capsys) -> None:
    ais = tmp_path / ".ais"
    (ais / "claude").mkdir(parents=True)

    exit_code = main(["--base-dir", str(tmp_path)])

    assert exit_code == 0
    assert "Dry run only" in capsys.readouterr().out
    assert ais.is_dir()
    assert not (tmp_path / ".engram").exists()


@patch("migrate_ais_to_engram._is_peer_leased", side_effect=_no_running_peers)
def test_main_apply_actually_moves(_mock, tmp_path: Path) -> None:
    ais = tmp_path / ".ais"
    (ais / "claude").mkdir(parents=True)

    exit_code = main(["--base-dir", str(tmp_path), "--apply"])

    assert exit_code == 0
    assert not ais.exists()
    assert (tmp_path / ".engram" / "claude").is_dir()


@patch("migrate_ais_to_engram._is_peer_leased", side_effect=_no_running_peers)
def test_main_returns_2_on_refusal(_mock, tmp_path: Path, capsys) -> None:
    ais = tmp_path / ".ais"
    ais.mkdir()
    (ais / "MANIFEST.txt").write_text("snapshot\n", encoding="utf-8")

    exit_code = main(["--base-dir", str(tmp_path), "--apply"])

    assert exit_code == 2
    assert "REFUSED" in capsys.readouterr().err
