"""Tests for provisioner.py's D10 ensure_tool/ensure_peer_cli auto-install path.

All filesystem operations happen under tmp_path (never the real _sys/tools).
Only the network boundary (_secure_download) and npm subprocess calls are
mocked; extraction, flattening, checksum, and manifest logic run for real.
"""
import json
import sys
import zipfile
from pathlib import Path

SYS_DIR = Path(__file__).resolve().parent.parent.parent  # _sys/
sys.path.insert(0, str(SYS_DIR / "core"))
import provisioner as pv  # noqa: E402


def _make_sys_dir(tmp_path: Path, tools: dict, peers: dict | None = None) -> Path:
    sys_dir = tmp_path / "_sys"
    sys_dir.mkdir()
    (sys_dir / "runtimes.json").write_text(
        json.dumps({"_comment": "test", "runtimes": {}, "tools": tools}), encoding="utf-8"
    )
    (sys_dir / "ai").mkdir()
    (sys_dir / "ai" / "peers.json").write_text(
        json.dumps({"peers": peers or {}}), encoding="utf-8"
    )
    (sys_dir / "tools").mkdir()
    (sys_dir / "data" / "setup-files").mkdir(parents=True)
    return sys_dir


def _make_fixture_zip(dest: Path, exe_name: str, nested: bool = True) -> None:
    with zipfile.ZipFile(dest, "w") as zf:
        arcname = f"{exe_name}-1.0.0/{exe_name}" if nested else exe_name
        zf.writestr(arcname, b"fake binary contents")


class TestEnsureToolZip:
    def test_missing_tool_installs_and_flattens_nested_zip(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {
            "ripgrep": {
                "version": "15.1.0",
                "url": "https://example/ripgrep.zip",
                "install_mechanism": "zip_tool",
                "bin": "rg.exe",
            }
        })

        def fake_download(url, dest_path):
            _make_fixture_zip(dest_path, "rg.exe", nested=True)

        monkeypatch.setattr(pv, "_secure_download", fake_download)

        res = pv.ensure_tool("ripgrep", sys_dir=sys_dir)

        assert res["status"] == "success"
        active_exe = sys_dir / "tools" / "ripgrep" / "rg.exe"
        assert active_exe.exists()
        assert active_exe.read_bytes() == b"fake binary contents"

        manifest = json.loads((sys_dir / "tools" / "ripgrep" / ".install_manifest.json").read_text(encoding="utf-8"))
        assert manifest["declared_version"] == "15.1.0"
        assert manifest["checksum_source"] == "computed_tls_trust"

        # temp dirs are gone, no _extract/_tmp leftovers
        leftovers = [p.name for p in (sys_dir / "tools").iterdir() if p.name != "ripgrep"]
        assert leftovers == []

    def test_already_current_skips_download(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {
            "ripgrep": {"version": "15.1.0", "url": "https://example/ripgrep.zip", "install_mechanism": "zip_tool"}
        })
        dest_dir = sys_dir / "tools" / "ripgrep"
        dest_dir.mkdir()
        (dest_dir / ".install_manifest.json").write_text(
            json.dumps({"declared_version": "15.1.0"}), encoding="utf-8"
        )

        called = []
        monkeypatch.setattr(pv, "_secure_download", lambda url, dest: called.append(url))

        res = pv.ensure_tool("ripgrep", sys_dir=sys_dir)

        assert res["status"] == "already_current"
        assert called == []

    def test_checksum_mismatch_is_governance_required_and_cleans_up(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {
            "ripgrep": {
                "version": "15.1.0",
                "url": "https://example/ripgrep.zip",
                "install_mechanism": "zip_tool",
                "sha256": "0" * 64,
            }
        })

        def fake_download(url, dest_path):
            dest_path.write_bytes(b"not the real file")

        monkeypatch.setattr(pv, "_secure_download", fake_download)

        res = pv.ensure_tool("ripgrep", sys_dir=sys_dir)

        assert res["status"] == "governance_required"
        assert "Checksum mismatch" in res["detail"]
        assert list((sys_dir / "tools").iterdir()) == []

    def test_unknown_tool_errors(self, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {})
        res = pv.ensure_tool("nonexistent", sys_dir=sys_dir)
        assert res["status"] == "error"


class TestEnsureToolExe:
    def test_exe_tool_mechanism_installs(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {
            "jq": {
                "version": "1.8.1",
                "url": "https://example/jq-windows-amd64.exe",
                "install_mechanism": "exe_tool",
                "bin": "jq.exe",
            }
        })

        def fake_download(url, dest_path):
            dest_path.write_bytes(b"fake jq binary")

        monkeypatch.setattr(pv, "_secure_download", fake_download)

        res = pv.ensure_tool("jq", sys_dir=sys_dir)

        assert res["status"] == "success"
        assert (sys_dir / "tools" / "jq" / "jq.exe").read_bytes() == b"fake jq binary"


class TestEnsurePeerCliNativeBinary:
    def test_antigravity_delegates_to_ensure_tool(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(
            tmp_path,
            tools={"agy": {"version": "1.0.7", "url": "https://example/agy.exe", "install_mechanism": "exe_tool"}},
            peers={
                "antigravity": {
                    "native_binary": {"bin_name": "agy", "win_exe": "agy.exe", "install_subdir": "tools/agy"},
                    "node_ids": ["ag"],
                }
            },
        )

        calls = []
        monkeypatch.setattr(pv, "ensure_tool", lambda name, orch=None, sys_dir=None: calls.append(name) or {"status": "success"})

        res = pv.ensure_peer_cli("antigravity", sys_dir=sys_dir)
        assert calls == ["agy"]
        assert res["status"] == "success"

    def test_resolves_via_node_id(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(
            tmp_path,
            tools={"agy": {"version": "1.0.7", "url": "https://example/agy.exe", "install_mechanism": "exe_tool"}},
            peers={
                "antigravity": {
                    "native_binary": {"bin_name": "agy", "win_exe": "agy.exe", "install_subdir": "tools/agy"},
                    "node_ids": ["ag"],
                }
            },
        )
        calls = []
        monkeypatch.setattr(pv, "ensure_tool", lambda name, orch=None, sys_dir=None: calls.append(name) or {"status": "success"})

        res = pv.ensure_peer_cli("ag", sys_dir=sys_dir)
        assert calls == ["agy"]
        assert res["status"] == "success"

    def test_unknown_peer_errors(self, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, tools={}, peers={})
        res = pv.ensure_peer_cli("nope", sys_dir=sys_dir)
        assert res["status"] == "error"


class TestEnsurePeerCliNpm:
    def _setup_npm_env(self, sys_dir: Path) -> None:
        node_exe = sys_dir / "env" / "nodejs" / "node.exe"
        node_exe.parent.mkdir(parents=True, exist_ok=True)
        node_exe.write_bytes(b"fake node")

    def test_npm_peer_installs_pinned_version(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(
            tmp_path,
            tools={"claude": {"version": "2.1.206", "discovery_id": "@anthropic-ai/claude-code", "install_mechanism": "npm_peer"}},
            peers={"claude": {"npm_package": "@anthropic-ai/claude-code", "node_ids": ["cc", "ca"]}},
        )
        self._setup_npm_env(sys_dir)

        calls = []

        class FakeCompleted:
            def __init__(self, stdout):
                self.stdout = stdout

        def fake_run(argv, **kwargs):
            calls.append(argv)
            if "view" in argv:
                return FakeCompleted('"sha512-fakeintegrity"')
            return FakeCompleted("")

        monkeypatch.setattr(pv.subprocess, "run", fake_run)

        res = pv.ensure_peer_cli("claude", sys_dir=sys_dir)

        assert res["status"] == "success"
        install_call = [c for c in calls if "install" in c][0]
        assert f"@anthropic-ai/claude-code@2.1.206" in install_call

        manifest = json.loads((sys_dir / "tools" / "claude" / ".install_manifest.json").read_text(encoding="utf-8"))
        assert manifest["declared_version"] == "2.1.206"
        assert manifest["checksum_source"] == "registry_integrity"

    def test_npm_peer_already_current_uses_peer_key_cmd_not_node_id(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(
            tmp_path,
            tools={
                "claude": {
                    "version": "2.1.206",
                    "discovery_id": "@anthropic-ai/claude-code",
                    "install_mechanism": "npm_peer",
                }
            },
            peers={
                "claude": {
                    "npm_package": "@anthropic-ai/claude-code",
                    "node_ids": ["cc", "ca"],
                }
            },
        )
        self._setup_npm_env(sys_dir)

        npm_global = sys_dir / "env" / "nodejs" / "npm-global"
        npm_global.mkdir(parents=True)
        (npm_global / "claude.cmd").write_text("@echo off\n", encoding="utf-8")

        manifest_dir = sys_dir / "tools" / "claude"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / ".install_manifest.json").write_text(
            json.dumps({"declared_version": "2.1.206"}),
            encoding="utf-8",
        )

        subprocess_calls = []

        def fail_if_called(*args, **kwargs):
            subprocess_calls.append((args, kwargs))
            raise AssertionError("already-current peer CLI must not invoke npm")

        monkeypatch.setattr(pv.subprocess, "run", fail_if_called)

        res = pv.ensure_peer_cli("claude", sys_dir=sys_dir)

        assert res["status"] == "already_current"
        assert subprocess_calls == []
        assert (npm_global / "claude.cmd").exists()
        assert not (npm_global / "cc.cmd").exists()

    def test_npm_peer_without_nodejs_errors(self, tmp_path):
        sys_dir = _make_sys_dir(
            tmp_path,
            tools={"claude": {"version": "2.1.206", "install_mechanism": "npm_peer"}},
            peers={"claude": {"npm_package": "@anthropic-ai/claude-code", "node_ids": ["cc"]}},
        )
        res = pv.ensure_peer_cli("claude", sys_dir=sys_dir)
        assert res["status"] == "error"
        assert "Node.js" in res["detail"]

    def test_npm_peer_without_declared_version_errors(self, tmp_path):
        sys_dir = _make_sys_dir(
            tmp_path,
            tools={},
            peers={"claude": {"npm_package": "@anthropic-ai/claude-code", "node_ids": ["cc"]}},
        )
        self._setup_npm_env(sys_dir)
        res = pv.ensure_peer_cli("claude", sys_dir=sys_dir)
        assert res["status"] == "error"
        assert "No version declared" in res["detail"]


class TestDeferredRetry:
    def test_add_load_remove_roundtrip(self, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {})
        pv._add_deferred(sys_dir, "ripgrep", "tool")
        data = pv._load_deferred(sys_dir)
        assert data == {"tool:ripgrep": {"kind": "tool", "name": "ripgrep"}}

        pv._remove_deferred(sys_dir, "ripgrep", "tool")
        assert pv._load_deferred(sys_dir) == {}


class TestLegacyInstallToolsCompatibility:
    def test_install_tools_skips_npm_peer_entries_without_url(self, monkeypatch, tmp_path):
        env_dir = tmp_path / "_sys" / "env"
        setup_dir = tmp_path / "_sys" / "data" / "setup-files"
        env_dir.mkdir(parents=True)
        setup_dir.mkdir(parents=True)

        tools = {
            "claude": {
                "version": "1.0.0",
                "install_mechanism": "npm_peer",
            },
            "ripgrep": {
                "version": "15.1.0",
                "url": "https://example.invalid/ripgrep.zip",
                "type": "zip",
                "bin": "rg.exe",
            },
        }

        download_calls = []

        def fake_download(url, dest, label):
            download_calls.append((url, label))
            dest.write_bytes(b"fake zip placeholder")

        def fake_extract(zip_path, dest):
            nested = dest / "ripgrep-15.1.0"
            nested.mkdir(parents=True)
            (nested / "rg.exe").write_bytes(b"fake rg binary")

        monkeypatch.setattr(pv, "_download", fake_download)
        monkeypatch.setattr(pv, "_extract", fake_extract)

        installed = pv._install_tools(tools, env_dir, setup_dir, force=False)

        assert installed == ["ripgrep"]
        assert download_calls == [("https://example.invalid/ripgrep.zip", "ripgrep")]
        assert (env_dir.parent / "tools" / "ripgrep" / "rg.exe").read_bytes() == b"fake rg binary"
        assert not (env_dir.parent / "tools" / "claude").exists()

    def test_lazy_drain_processes_and_clears_queue(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {})
        pv._add_deferred(sys_dir, "ripgrep", "tool")

        calls = []
        monkeypatch.setattr(pv, "ensure_tool", lambda name, orch=None, sys_dir=None: calls.append(name))

        pv._drain_deferred_lazy(None, sys_dir)

        assert calls == ["ripgrep"]
        assert pv._load_deferred(sys_dir) == {}
