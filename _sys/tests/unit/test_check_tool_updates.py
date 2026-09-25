# _sys/tests/unit/test_check_tool_updates.py
from __future__ import annotations

import json
import sys
from pathlib import Path

from _sys.core.root import find_root

SYS_DIR = find_root(__file__)
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
        "section": "tools",
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


def test_apply_install_success_runs_bootstrap_bat_skip_update(monkeypatch, tmp_path):
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
    assert str(calls[0][0][0]).endswith(r"_sys\core\bootstrap.bat")


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


def test_check_tool_updates_renamed_sys_dir_safe(monkeypatch, tmp_path):
    """Verify that state and cache paths are rooted under renamed sys_dir, not literal _sys."""
    inst = tmp_path / "inst"
    sys_dir = inst / "my_runtime"
    sys_dir.mkdir(parents=True)

    from _sys.core import state_paths

    archive_root = state_paths.proposals_dir(sys_dir)
    cache_path = state_paths.discovery_cache(sys_dir)

    assert archive_root == sys_dir / "data" / "state" / "update" / "proposals"
    assert cache_path == sys_dir / "data" / "state" / "update" / "tool_discovery_cache.json"
    assert not (inst / "_sys").exists()
    assert str(archive_root).startswith(str(sys_dir))
    assert str(cache_path).startswith(str(sys_dir))

    monkeypatch.setattr(ctu, "_SYS_DIR", sys_dir)
    monkeypatch.setattr(ctu, "ARCHIVE_ROOT", state_paths.proposals_dir(sys_dir))
    monkeypatch.setattr(ctu, "DISCOVERY_CACHE_PATH", state_paths.discovery_cache(sys_dir))

    assert ctu.ARCHIVE_ROOT == sys_dir / "data" / "state" / "update" / "proposals"
    assert ctu.DISCOVERY_CACHE_PATH == sys_dir / "data" / "state" / "update" / "tool_discovery_cache.json"
    assert not str(ctu.ARCHIVE_ROOT).startswith(str(inst / "_sys"))
    assert not str(ctu.DISCOVERY_CACHE_PATH).startswith(str(inst / "_sys"))

    # Test bootstrap invocation uses renamed sys folder name
    monkeypatch.setattr(ctu, "_PORTABLE_ROOT", inst)
    calls = []
    monkeypatch.setattr(
        ctu.subprocess,
        "run",
        lambda args, cwd=None, capture_output=None, text=None: (
            calls.append((args, cwd)),
            ctu.subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr=""),
        )[1],
    )
    ctu._run_install_step()
    assert len(calls) == 1
    cmd_args, cwd = calls[0]
    assert cmd_args[0] == rf".\{sys_dir.name}\core\bootstrap.bat"
    assert cwd == str(inst)
    assert not (inst / "_sys").exists()


def test_run_with_only_filters_tools(monkeypatch, tmp_path):
    runtimes_path = tmp_path / "runtimes.json"
    _write_runtimes(runtimes_path)
    monkeypatch.setattr(ctu, "RUNTIMES_PATH", runtimes_path)
    monkeypatch.setattr(ctu, "ARCHIVE_ROOT", tmp_path / "proposals")
    monkeypatch.setattr(ctu, "DISCOVERY_CACHE_PATH", tmp_path / "cache.json")

    resolved_tools = []
    monkeypatch.setattr(
        ctu.version_resolver,
        "resolve_latest",
        lambda tool_name, provider, current_version, discovery_id, cache_path=None: (
            resolved_tools.append(tool_name),
            {
                "status": "ok",
                "tool": tool_name,
                "provider": provider,
                "discovery_id": discovery_id,
                "latest_version": current_version,
            }
        )[1],
    )

    ctu.run(propose_diff=False, only=["ripgrep"])
    assert resolved_tools == ["ripgrep"]


def test_discover_updates_normalizes_comma_separated_only(monkeypatch, tmp_path):
    runtimes_path = tmp_path / "runtimes.json"
    _write_runtimes(runtimes_path)
    monkeypatch.setattr(ctu, "RUNTIMES_PATH", runtimes_path)
    monkeypatch.setattr(ctu, "ARCHIVE_ROOT", tmp_path / "proposals")
    monkeypatch.setattr(ctu, "DISCOVERY_CACHE_PATH", tmp_path / "cache.json")

    resolved_tools = []
    monkeypatch.setattr(
        ctu.version_resolver,
        "resolve_latest",
        lambda tool_name, provider, current_version, discovery_id, cache_path=None: (
            resolved_tools.append(tool_name),
            {
                "status": "ok",
                "tool": tool_name,
                "provider": provider,
                "discovery_id": discovery_id,
                "latest_version": current_version,
            }
        )[1],
    )

    ctu.discover_updates(only=["ripgrep,bat", "gh"])
    assert "ripgrep" in resolved_tools
    assert "bat" in resolved_tools
    assert "gh" in resolved_tools


def test_discover_updates_includes_section_in_discovered_updates(monkeypatch, tmp_path):
    runtimes_path = tmp_path / "runtimes.json"
    _write_runtimes(runtimes_path)
    monkeypatch.setattr(ctu, "RUNTIMES_PATH", runtimes_path)
    monkeypatch.setattr(ctu, "ARCHIVE_ROOT", tmp_path / "proposals")
    monkeypatch.setattr(ctu, "DISCOVERY_CACHE_PATH", tmp_path / "cache.json")

    monkeypatch.setattr(
        ctu.version_resolver,
        "resolve_latest",
        lambda tool_name, provider, current_version, discovery_id, cache_path=None: {
            "status": "ok",
            "tool": tool_name,
            "provider": provider,
            "discovery_id": discovery_id,
            "latest_version": "99.99.99",
        },
    )

    payload, *_ = ctu.discover_updates(only=["ripgrep"])
    assert len(payload["updates_discovered"]) == 1
    assert payload["updates_discovered"][0]["section"] == "tools"
    assert payload["updates_discovered"][0]["tool"] == "ripgrep"


def test_unknown_only_name_validation_exits_before_network(monkeypatch, tmp_path):
    runtimes_path = tmp_path / "runtimes.json"
    _write_runtimes(runtimes_path)
    monkeypatch.setattr(ctu, "RUNTIMES_PATH", runtimes_path)

    resolver_called = False
    def mock_resolve(*args, **kwargs):
        nonlocal resolver_called
        resolver_called = True
        return {"status": "ok", "latest_version": "1.0"}

    monkeypatch.setattr(ctu.version_resolver, "resolve_latest", mock_resolve)

    payload, *_ = ctu.discover_updates(only=["completely_bogus_tool_xyz"])
    assert resolver_called is False
    assert len(payload["errors"]) == 1
    assert "Unknown component in --only" in payload["errors"][0]["error"]

    # Test main() exit code 2
    monkeypatch.setattr(ctu, "run", lambda **kwargs: payload)
    exit_code = ctu.main(["--only", "completely_bogus_tool_xyz"])
    assert exit_code == ctu.EXIT_INVALID_PROPOSAL  # 2


def test_main_forwards_only_flag(monkeypatch):
    captured_only = None
    def mock_run(*, propose_diff=False, only=None):
        nonlocal captured_only
        captured_only = only
        return {
            "artifact_dir": None,
            "base_sha256": None,
            "updates_discovered": [],
            "up_to_date": [],
            "rate_limited": [],
            "errors": [],
            "not_checked": [],
        }
    monkeypatch.setattr(ctu, "run", mock_run)
    exit_code = ctu.main(["--only", "ripgrep", "bat"])
    assert exit_code == ctu.EXIT_OK
    assert captured_only == ["ripgrep", "bat"]


def test_main_forwards_refresh_flag(monkeypatch):
    captured_refresh = None
    def mock_run(*, propose_diff=False, only=None, force_refresh=False, **kwargs):
        nonlocal captured_refresh
        captured_refresh = force_refresh
        return {
            "artifact_dir": None,
            "base_sha256": None,
            "updates_discovered": [],
            "up_to_date": [],
            "rate_limited": [],
            "errors": [],
            "not_checked": [],
        }
    monkeypatch.setattr(ctu, "run", mock_run)
    exit_code = ctu.main(["--refresh"])
    assert exit_code == ctu.EXIT_OK
    assert captured_refresh is True




