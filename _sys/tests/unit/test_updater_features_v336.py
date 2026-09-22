import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from core import version_resolver, provisioner, updater, doctor
from checks import check_tool_updates


def test_resolve_vscode_official():
    mock_payload = {
        "name": "1.100.2",
        "url": "https://update.code.visualstudio.com/1.100.2/win32-x64-archive/stable",
        "sha256hash": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    }
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp

        res = version_resolver._resolve_vscode("win32-x64-archive")
        assert res["status"] == "ok"
        assert res["latest_version"] == "1.100.2"
        assert res["checksum_algo"] == "sha256"
        assert res["checksum_value"] == "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        assert res["source"] == "vscode_official"


def test_resolve_nodejs_lts():
    mock_index = [
        {"version": "v25.0.0", "lts": False, "files": ["win-x64-zip"]},
        {"version": "v24.21.0", "lts": "Hydrogen", "files": ["win-x64-zip"]},
        {"version": "v22.14.0", "lts": "Iron", "files": ["win-x64-zip"]},
    ]
    mock_shasums = "112233445566778899aabbccddeeff00112233445566778899aabbccddeeff00  node-v24.21.0-win-x64.zip\n"
    with patch("urllib.request.urlopen") as mock_url:
        resp1 = MagicMock()
        resp1.getcode.return_value = 200
        resp1.read.return_value = json.dumps(mock_index).encode("utf-8")
        resp1.__enter__.return_value = resp1

        resp2 = MagicMock()
        resp2.getcode.return_value = 200
        resp2.read.return_value = mock_shasums.encode("utf-8")
        resp2.__enter__.return_value = resp2

        mock_url.side_effect = [resp1, resp2]

        res = version_resolver._resolve_nodejs_lts("lts")
        assert res["status"] == "ok"
        assert res["latest_version"] == "24.21.0"
        assert "node-v24.21.0-win-x64.zip" in res["url"]
        assert res["checksum_value"] == "112233445566778899aabbccddeeff00112233445566778899aabbccddeeff00"


def test_resolve_github_releases_exact_asset_pattern(tmp_path, monkeypatch):
    monkeypatch.setattr(version_resolver.shutil, "which", lambda name: None)
    mock_release = {
        "tag_name": "v7.6.2",
        "assets": [
            {"name": "PowerShell-7.6.2-linux-x64.tar.gz", "browser_download_url": "http://example/linux"},
            {"name": "PowerShell-7.6.2-win-x64.zip", "browser_download_url": "http://example/pwsh-win.zip"},
            {"name": "PowerShell-7.6.2-win-x86.zip", "browser_download_url": "http://example/pwsh-win86.zip"},
        ],
    }
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.headers = {}
        mock_resp.read.return_value = json.dumps(mock_release).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp

        res = version_resolver._resolve_github(
            "PowerShell/PowerShell",
            cache_path=tmp_path / "cache.json",
            asset_pattern=r"^PowerShell-[0-9.]+-win-x64\.zip$",
        )
        assert res["status"] == "ok"
        assert res["latest_version"] == "7.6.2"
        assert res["url"] == "http://example/pwsh-win.zip"


def test_nodejs_major_upgrade_requires_opt_in(tmp_path, monkeypatch):
    mock_runtimes = {
        "runtimes": {
            "nodejs": {
                "version": "22.14.0",
                "discovery_provider": "nodejs_lts",
                "discovery_id": "lts",
            }
        }
    }
    runtimes_file = tmp_path / "runtimes.json"
    runtimes_file.write_text(json.dumps(mock_runtimes), encoding="utf-8")
    monkeypatch.setattr(check_tool_updates, "RUNTIMES_PATH", runtimes_file)
    monkeypatch.setattr(check_tool_updates, "CATALOG_PATH", tmp_path / "nonexistent.json")

    def fake_resolve(*args, **kwargs):
        return {
            "status": "ok",
            "latest_version": "24.21.0",
            "url": "https://example.com/node.zip",
            "checksum_algo": "sha256",
            "checksum_value": "abc",
        }
    monkeypatch.setattr(version_resolver, "resolve_latest", fake_resolve)

    # Without allow_major_runtime_upgrade: should be notice only
    payload, runtimes, proposed, catalog, proposed_catalog = check_tool_updates.discover_updates(allow_major_runtime_upgrade=False)
    assert not payload["updates_discovered"]
    assert any("Node.js major upgrade" in n.get("detail", "") for n in payload["notices"])

    # With allow_major_runtime_upgrade=True: should be included in updates_discovered
    payload, runtimes, proposed, catalog, proposed_catalog = check_tool_updates.discover_updates(allow_major_runtime_upgrade=True)
    assert len(payload["updates_discovered"]) == 1
    assert payload["updates_discovered"][0]["tool"] == "nodejs"
    assert payload["updates_discovered"][0]["latest_version"] == "24.21.0"


def test_python_is_notice_only(tmp_path, monkeypatch):
    mock_runtimes = {
        "runtimes": {
            "python": {
                "version": "3.14.0",
                "discovery_provider": "endoflife_python",
                "discovery_id": "python",
            }
        }
    }
    runtimes_file = tmp_path / "runtimes.json"
    runtimes_file.write_text(json.dumps(mock_runtimes), encoding="utf-8")
    monkeypatch.setattr(check_tool_updates, "RUNTIMES_PATH", runtimes_file)
    monkeypatch.setattr(check_tool_updates, "CATALOG_PATH", tmp_path / "nonexistent.json")

    def fake_resolve(*args, **kwargs):
        return {
            "status": "ok",
            "latest_version": "3.14.5",
            "detail": "notice_only",
        }
    monkeypatch.setattr(version_resolver, "resolve_latest", fake_resolve)

    payload, runtimes, proposed, catalog, proposed_catalog = check_tool_updates.discover_updates()
    assert not payload["updates_discovered"]
    assert any(n.get("component") == "python" for n in payload["notices"])


def test_self_update_peer_agy(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    tools_dir = sys_dir / "tools" / "agy"
    tools_dir.mkdir(parents=True)
    bin_path = tools_dir / "agy.exe"
    bin_path.write_bytes(b"MZfakebinary")

    catalog_data = {
        "tools": [
            {
                "tool_id": "agy",
                "version": "1.1.5",
                "install": {"mechanism": "exe_tool", "bin": "agy.exe"},
                "update": {
                    "mechanism": "self_update",
                    "bin": "agy.exe",
                    "argv": ["update"],
                    "version_argv": ["--version"],
                },
            }
        ]
    }
    catalog_path = sys_dir / "tool-catalog.v1.json"
    catalog_path.write_text(json.dumps(catalog_data), encoding="utf-8")

    call_count = 0
    def mock_subprocess_run(cmd, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        res = MagicMock()
        res.returncode = 0
        if "--version" in cmd:
            res.stdout = "1.2.8" if call_count > 1 else "1.1.5"
            res.stderr = ""
        else:
            res.stdout = "Updating agy... done"
            res.stderr = ""
        return res

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    res = provisioner.self_update_peer("agy", sys_dir=sys_dir)
    assert res["status"] == "success"
    assert "1.1.5 -> 1.2.8" in res["detail"]

    # Verify catalog is untouched!
    saved_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert saved_catalog["tools"][0]["version"] == "1.1.5"

    # Verify manifest has observed_version!
    manifest_path = tools_dir / ".install_manifest.json"
    assert manifest_path.exists()
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["observed_version"] == "1.2.8"

    # Verify doctor reports observed_version!
    rt_file = sys_dir / "runtimes.json"
    rt_file.write_text(json.dumps({"runtimes": {}, "tools": {}}), encoding="utf-8")
    doc_res = doctor.check_components(sys_dir)
    assert "agy: active 1.2.8" in doc_res["detail"]
    assert doc_res["observed_versions"].get("agy") == "1.2.8"


def test_self_update_peer_deferred_when_in_use(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    catalog_data = {
        "tools": [
            {
                "tool_id": "agy",
                "version": "1.1.5",
                "install": {"mechanism": "exe_tool", "bin": "agy.exe"},
                "update": {"mechanism": "self_update", "bin": "agy.exe"},
            }
        ]
    }
    (sys_dir / "tools" / "agy").mkdir(parents=True)
    (sys_dir / "tool-catalog.v1.json").write_text(json.dumps(catalog_data), encoding="utf-8")

    monkeypatch.setattr(provisioner, "_is_component_in_use", lambda sys_dir, tool: True)

    res = provisioner.self_update_peer("agy", sys_dir=sys_dir)
    assert res["status"] == "in_use_deferred"


def test_updater_run_agy_self_update(tmp_path, monkeypatch, capsys):
    sys_dir = tmp_path / "_sys"
    tools_dir = sys_dir / "tools" / "agy"
    tools_dir.mkdir(parents=True)
    bin_path = tools_dir / "agy.exe"
    bin_path.write_bytes(b"MZfakebinary")

    catalog_data = {
        "tools": [
            {
                "tool_id": "agy",
                "version": "1.1.5",
                "install": {"mechanism": "exe_tool", "bin": "agy.exe"},
                "update": {
                    "mechanism": "self_update",
                    "bin": "agy.exe",
                    "argv": ["update"],
                    "version_argv": ["--version"],
                },
            }
        ]
    }
    catalog_path = sys_dir / "tool-catalog.v1.json"
    catalog_path.write_text(json.dumps(catalog_data), encoding="utf-8")
    rt_path = sys_dir / "runtimes.json"
    rt_path.write_text(json.dumps({"runtimes": {}, "tools": {}}), encoding="utf-8")

    monkeypatch.setattr(updater, "_SYS_DIR", sys_dir)
    monkeypatch.setattr(updater, "_PORTABLE_ROOT", tmp_path)
    monkeypatch.setattr("core.updater.check_components", lambda s: {})

    monkeypatch.setattr(check_tool_updates, "run", lambda **kw: {
        "artifact_dir": str(tmp_path / "artifacts"),
        "updates_discovered": [],
        "not_checked": [],
        "errors": [],
    })
    monkeypatch.setattr(check_tool_updates, "apply_proposal", lambda *a, **kw: (0, {"applied": True}))
    monkeypatch.setattr(provisioner, "deploy", lambda ctx: {"status": "success", "installed": [], "failed": [], "deferred": []})

    updated_called = False
    def mock_self_update(tool_id, sys_dir=None):
        nonlocal updated_called
        updated_called = True
        return {"status": "success", "detail": "1.1.5 -> 1.2.8"}
    monkeypatch.setattr(provisioner, "self_update_peer", mock_self_update)

    res = updater.run({"args": ["--yes", "--only", "agy"]})
    assert res["status"] == "success"
    assert updated_called
    out = capsys.readouterr().out
    assert "Updating agy (in-place)..." in out
    assert "[OK] agy updated: 1.1.5 -> 1.2.8" in out

