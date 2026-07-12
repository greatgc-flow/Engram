# _sys/tests/unit/test_check_tool_updates.py
from __future__ import annotations

import json
import sys
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYS_DIR / "checks"))
sys.path.insert(0, str(SYS_DIR / "core"))

import check_tool_updates as ctu  # noqa: E402


def _write_runtimes(path: Path) -> dict:
    data = {
        "_comment": "test runtimes",
        "tools": {
            "ripgrep": {
                "version": "1.0.0",
                "url": "https://example/rg-old.zip",
                "type": "zip",
                "discovery_provider": "github_releases",
                "discovery_id": "BurntSushi/ripgrep",
            },
            "bat": {
                "version": "2.0.0",
                "url": "https://example/bat.zip",
                "type": "zip",
                "discovery_provider": "github_releases",
                "discovery_id": "sharkdp/bat",
            },
            "gh": {
                "version": "3.0.0",
                "url": "https://example/gh.zip",
                "type": "zip",
                "discovery_provider": "github_releases",
                "discovery_id": "cli/cli",
            },
            "agy": {
                "version": "1.0.0",
                "url": "https://example/agy.exe",
                "type": "exe",
                "discovery_provider": "manual",
            },
        },
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def test_propose_diff_never_touches_real_runtimes_and_writes_artifacts(monkeypatch, tmp_path):
    runtimes_path = tmp_path / "runtimes.json"
    original = _write_runtimes(runtimes_path)
    original_text = runtimes_path.read_text(encoding="utf-8")

    monkeypatch.setattr(ctu, "RUNTIMES_PATH", runtimes_path)
    monkeypatch.setattr(ctu, "ARCHIVE_ROOT", tmp_path / "_archive" / "tool-updates")
    monkeypatch.setattr(ctu, "DISCOVERY_CACHE_PATH", tmp_path / ".ai" / "tool_discovery_cache.json")

    def fake_resolve_latest(tool_name, provider, current_version, discovery_id, cache_path=None):
        if tool_name == "ripgrep":
            return {
                "status": "ok",
                "tool": tool_name,
                "provider": provider,
                "discovery_id": discovery_id,
                "latest_version": "1.1.0",
                "url": "https://example/rg-new.zip",
                "checksum_algo": "sha256",
                "checksum_value": "abc123",
            }
        if tool_name == "bat":
            return {
                "status": "ok",
                "tool": tool_name,
                "provider": provider,
                "discovery_id": discovery_id,
                "latest_version": current_version,
                "url": "https://example/bat.zip",
            }
        if tool_name == "gh":
            return {
                "status": "discovery_unavailable",
                "tool": tool_name,
                "provider": provider,
                "discovery_id": discovery_id,
                "error_type": "rate_limited",
            }
        raise AssertionError(tool_name)

    monkeypatch.setattr(ctu.version_resolver, "resolve_latest", fake_resolve_latest)

    payload = ctu.run(propose_diff=True)

    assert runtimes_path.read_text(encoding="utf-8") == original_text
    assert payload["updates_discovered"] == [{
        "tool": "ripgrep",
        "current_version": "1.0.0",
        "latest_version": "1.1.0",
        "url": "https://example/rg-new.zip",
        "checksum_algo": "sha256",
        "checksum_value": "abc123",
    }]
    assert payload["up_to_date"] == ["bat"]
    assert payload["rate_limited"] == ["gh"]
    assert payload["errors"] == []

    artifact_dir = Path(payload["artifact_dir"])
    assert artifact_dir.exists()
    assert (artifact_dir / "proposal.json").exists()
    assert (artifact_dir / "runtimes.proposed.json").exists()
    assert (artifact_dir / "runtimes.diff").exists()

    proposal = json.loads((artifact_dir / "proposal.json").read_text(encoding="utf-8"))
    assert proposal["base_sha256"] == ctu._sha256_file(runtimes_path)

    proposed = json.loads((artifact_dir / "runtimes.proposed.json").read_text(encoding="utf-8"))
    assert proposed["tools"]["ripgrep"]["version"] == "1.1.0"
    assert proposed["tools"]["ripgrep"]["url"] == "https://example/rg-new.zip"
    assert proposed["tools"]["ripgrep"]["sha256"] == "abc123"
    assert original["tools"]["ripgrep"]["version"] == "1.0.0"

    diff = (artifact_dir / "runtimes.diff").read_text(encoding="utf-8")
    assert "-            \"version\": \"1.0.0\"" in diff
    assert "+            \"version\": \"1.1.0\"" in diff


def test_verify_proposal_still_valid_accepts_fresh_and_rejects_stale(monkeypatch, tmp_path):
    runtimes_path = tmp_path / "runtimes.json"
    _write_runtimes(runtimes_path)

    monkeypatch.setattr(ctu, "RUNTIMES_PATH", runtimes_path)
    monkeypatch.setattr(ctu, "ARCHIVE_ROOT", tmp_path / "_archive" / "tool-updates")
    monkeypatch.setattr(ctu, "DISCOVERY_CACHE_PATH", tmp_path / ".ai" / "tool_discovery_cache.json")

    monkeypatch.setattr(
        ctu.version_resolver,
        "resolve_latest",
        lambda tool_name, provider, current_version, discovery_id, cache_path=None: {
            "status": "ok",
            "tool": tool_name,
            "provider": provider,
            "discovery_id": discovery_id,
            "latest_version": current_version,
        },
    )

    payload = ctu.run(propose_diff=True)
    artifact_dir = Path(payload["artifact_dir"])

    assert ctu.verify_proposal_still_valid(artifact_dir) is True

    data = json.loads(runtimes_path.read_text(encoding="utf-8"))
    data["tools"]["ripgrep"]["version"] = "9.9.9"
    runtimes_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    assert ctu.verify_proposal_still_valid(artifact_dir) is False


def test_apply_rejects_path_traversal_and_does_not_touch_runtimes(monkeypatch, tmp_path):
    runtimes_path = tmp_path / "runtimes.json"
    _write_runtimes(runtimes_path)
    original_text = runtimes_path.read_text(encoding="utf-8")

    archive_root = tmp_path / "_archive" / "tool-updates"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "proposal.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(ctu, "RUNTIMES_PATH", runtimes_path)
    monkeypatch.setattr(ctu, "ARCHIVE_ROOT", archive_root)

    code, payload = ctu.apply_proposal(outside, yes=True)

    assert code == 2
    assert payload["applied"] is False
    assert "path rejected" in payload["errors"][0]
    assert runtimes_path.read_text(encoding="utf-8") == original_text


def test_apply_rejects_stale_proposal_and_does_not_touch_runtimes(monkeypatch, tmp_path):
    runtimes_path = tmp_path / "runtimes.json"
    _write_runtimes(runtimes_path)

    monkeypatch.setattr(ctu, "RUNTIMES_PATH", runtimes_path)
    monkeypatch.setattr(ctu, "ARCHIVE_ROOT", tmp_path / "_archive" / "tool-updates")
    monkeypatch.setattr(ctu, "DISCOVERY_CACHE_PATH", tmp_path / ".ai" / "tool_discovery_cache.json")

    monkeypatch.setattr(
        ctu.version_resolver,
        "resolve_latest",
        lambda tool_name, provider, current_version, discovery_id, cache_path=None: {
            "status": "ok",
            "tool": tool_name,
            "provider": provider,
            "discovery_id": discovery_id,
            "latest_version": "1.1.0" if tool_name == "ripgrep" else current_version,
            "url": "https://example/rg-new.zip" if tool_name == "ripgrep" else None,
        },
    )

    payload = ctu.run(propose_diff=True)
    artifact_dir = Path(payload["artifact_dir"])

    data = json.loads(runtimes_path.read_text(encoding="utf-8"))
    data["tools"]["ripgrep"]["version"] = "9.9.9"
    stale_text = json.dumps(data, ensure_ascii=False, indent=2)
    runtimes_path.write_text(stale_text, encoding="utf-8")

    code, apply_payload = ctu.apply_proposal(artifact_dir, yes=True)

    assert code == 2
    assert apply_payload["applied"] is False
    assert "stale proposal" in apply_payload["errors"][0]
    assert runtimes_path.read_text(encoding="utf-8") == stale_text


def test_apply_without_yes_reports_planned_change_and_does_not_touch_runtimes(monkeypatch, tmp_path):
    runtimes_path = tmp_path / "runtimes.json"
    _write_runtimes(runtimes_path)
    original_text = runtimes_path.read_text(encoding="utf-8")

    monkeypatch.setattr(ctu, "RUNTIMES_PATH", runtimes_path)
    monkeypatch.setattr(ctu, "ARCHIVE_ROOT", tmp_path / "_archive" / "tool-updates")
    monkeypatch.setattr(ctu, "DISCOVERY_CACHE_PATH", tmp_path / ".ai" / "tool_discovery_cache.json")

    monkeypatch.setattr(
        ctu.version_resolver,
        "resolve_latest",
        lambda tool_name, provider, current_version, discovery_id, cache_path=None: {
            "status": "ok",
            "tool": tool_name,
            "provider": provider,
            "discovery_id": discovery_id,
            "latest_version": "1.1.0" if tool_name == "ripgrep" else current_version,
            "url": "https://example/rg-new.zip" if tool_name == "ripgrep" else None,
        },
    )

    payload = ctu.run(propose_diff=True)
    code, apply_payload = ctu.apply_proposal(Path(payload["artifact_dir"]), yes=False)

    assert code == 3
    assert apply_payload["applied"] is False
    assert apply_payload["confirmation_required"] is True
    assert "ripgrep: 1.0.0 -> 1.1.0" in apply_payload["planned_changes"]
    assert runtimes_path.read_text(encoding="utf-8") == original_text


def test_apply_yes_writes_backup_and_replaces_runtimes_with_proposed(monkeypatch, tmp_path):
    runtimes_path = tmp_path / "runtimes.json"
    original = _write_runtimes(runtimes_path)

    monkeypatch.setattr(ctu, "RUNTIMES_PATH", runtimes_path)
    monkeypatch.setattr(ctu, "ARCHIVE_ROOT", tmp_path / "_archive" / "tool-updates")
    monkeypatch.setattr(ctu, "DISCOVERY_CACHE_PATH", tmp_path / ".ai" / "tool_discovery_cache.json")

    monkeypatch.setattr(
        ctu.version_resolver,
        "resolve_latest",
        lambda tool_name, provider, current_version, discovery_id, cache_path=None: {
            "status": "ok",
            "tool": tool_name,
            "provider": provider,
            "discovery_id": discovery_id,
            "latest_version": "1.1.0" if tool_name == "ripgrep" else current_version,
            "url": "https://example/rg-new.zip" if tool_name == "ripgrep" else None,
            "checksum_algo": "sha256" if tool_name == "ripgrep" else None,
            "checksum_value": "abc123" if tool_name == "ripgrep" else None,
        },
    )

    payload = ctu.run(propose_diff=True)
    artifact_dir = Path(payload["artifact_dir"])
    proposed = json.loads((artifact_dir / "runtimes.proposed.json").read_text(encoding="utf-8"))

    code, apply_payload = ctu.apply_proposal(artifact_dir, yes=True)

    assert code == 0
    assert apply_payload["applied"] is True
    assert (artifact_dir / "runtimes.json.bak").exists()
    backup = json.loads((artifact_dir / "runtimes.json.bak").read_text(encoding="utf-8"))
    assert backup == original
    current = json.loads(runtimes_path.read_text(encoding="utf-8"))
    assert current == proposed


def test_apply_install_success_runs_install_bat_skip_update(monkeypatch, tmp_path):
    runtimes_path = tmp_path / "runtimes.json"
    _write_runtimes(runtimes_path)

    monkeypatch.setattr(ctu, "RUNTIMES_PATH", runtimes_path)
    monkeypatch.setattr(ctu, "ARCHIVE_ROOT", tmp_path / "_archive" / "tool-updates")
    monkeypatch.setattr(ctu, "DISCOVERY_CACHE_PATH", tmp_path / ".ai" / "tool_discovery_cache.json")

    monkeypatch.setattr(
        ctu.version_resolver,
        "resolve_latest",
        lambda tool_name, provider, current_version, discovery_id, cache_path=None: {
            "status": "ok",
            "tool": tool_name,
            "provider": provider,
            "discovery_id": discovery_id,
            "latest_version": "1.1.0" if tool_name == "ripgrep" else current_version,
            "url": "https://example/rg-new.zip" if tool_name == "ripgrep" else None,
        },
    )

    calls = []
    def fake_run(args, cwd=None, capture_output=None, text=None):
        calls.append((args, cwd, capture_output, text))
        return ctu.subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(ctu.subprocess, "run", fake_run)

    payload = ctu.run(propose_diff=True)
    code, apply_payload = ctu.apply_proposal(Path(payload["artifact_dir"]), yes=True, install=True)

    assert code == 0
    assert apply_payload["applied"] is True
    assert apply_payload["install_succeeded"] is True
    assert calls
    assert calls[0][0][-1] == "--skip-update"
    assert str(calls[0][0][0]).endswith("INSTALL.bat")


def test_apply_install_failure_returns_4_after_successful_apply(monkeypatch, tmp_path):
    runtimes_path = tmp_path / "runtimes.json"
    _write_runtimes(runtimes_path)

    monkeypatch.setattr(ctu, "RUNTIMES_PATH", runtimes_path)
    monkeypatch.setattr(ctu, "ARCHIVE_ROOT", tmp_path / "_archive" / "tool-updates")
    monkeypatch.setattr(ctu, "DISCOVERY_CACHE_PATH", tmp_path / ".ai" / "tool_discovery_cache.json")

    monkeypatch.setattr(
        ctu.version_resolver,
        "resolve_latest",
        lambda tool_name, provider, current_version, discovery_id, cache_path=None: {
            "status": "ok",
            "tool": tool_name,
            "provider": provider,
            "discovery_id": discovery_id,
            "latest_version": "1.1.0" if tool_name == "ripgrep" else current_version,
            "url": "https://example/rg-new.zip" if tool_name == "ripgrep" else None,
        },
    )

    monkeypatch.setattr(
        ctu.subprocess,
        "run",
        lambda args, cwd=None, capture_output=None, text=None: ctu.subprocess.CompletedProcess(
            args=args, returncode=9, stdout="", stderr="install failed"
        ),
    )

    payload = ctu.run(propose_diff=True)
    proposed = json.loads((Path(payload["artifact_dir"]) / "runtimes.proposed.json").read_text(encoding="utf-8"))

    code, apply_payload = ctu.apply_proposal(Path(payload["artifact_dir"]), yes=True, install=True)

    assert code == 4
    assert apply_payload["applied"] is True
    assert apply_payload["install_succeeded"] is False
    assert apply_payload["install_returncode"] == 9
    assert json.loads(runtimes_path.read_text(encoding="utf-8")) == proposed
