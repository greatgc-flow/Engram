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
        cfg = {"version": "15.1.0", "url": "https://example/ripgrep.zip", "install_mechanism": "zip_tool"}
        sys_dir = _make_sys_dir(tmp_path, {"ripgrep": cfg})
        dest_dir = sys_dir / "tools" / "ripgrep"
        dest_dir.mkdir()
        (dest_dir / "ripgrep.exe").write_bytes(b"already installed")
        (dest_dir / ".install_manifest.json").write_text(
            json.dumps({"declared_version": "15.1.0", "source_config_hash": pv._canon_hash(cfg)}),
            encoding="utf-8",
        )

        called = []
        monkeypatch.setattr(pv, "_secure_download", lambda url, dest: called.append(url))

        res = pv.ensure_tool("ripgrep", sys_dir=sys_dir)

        assert res["status"] == "already_current"
        assert called == []

    def test_already_current_reinstalls_when_source_config_hash_changed(self, monkeypatch, tmp_path):
        """D11: a URL/checksum/canary change with no version bump must still
        be detected and trigger a reinstall (the version-only check used to
        miss this)."""
        cfg = {"version": "15.1.0", "url": "https://example/ripgrep-NEW.zip", "install_mechanism": "zip_tool"}
        sys_dir = _make_sys_dir(tmp_path, {"ripgrep": cfg})
        dest_dir = sys_dir / "tools" / "ripgrep"
        dest_dir.mkdir()
        (dest_dir / "ripgrep.exe").write_bytes(b"already installed")
        (dest_dir / ".install_manifest.json").write_text(
            json.dumps({"declared_version": "15.1.0", "source_config_hash": "stale-hash-from-old-url"}),
            encoding="utf-8",
        )

        def fake_download(url, dest_path):
            with zipfile.ZipFile(dest_path, "w") as zf:
                zf.writestr("ripgrep.exe", b"reinstalled")

        monkeypatch.setattr(pv, "_secure_download", fake_download)

        res = pv.ensure_tool("ripgrep", sys_dir=sys_dir)

        assert res["status"] == "success"
        assert (dest_dir / "ripgrep.exe").read_bytes() == b"reinstalled"

    def test_already_current_reinstalls_when_binary_missing(self, monkeypatch, tmp_path):
        """D11: a manually-deleted binary must not be silently reported as
        already_current just because the manifest still matches."""
        cfg = {"version": "15.1.0", "url": "https://example/ripgrep.zip", "install_mechanism": "zip_tool"}
        sys_dir = _make_sys_dir(tmp_path, {"ripgrep": cfg})
        dest_dir = sys_dir / "tools" / "ripgrep"
        dest_dir.mkdir()
        (dest_dir / ".install_manifest.json").write_text(
            json.dumps({"declared_version": "15.1.0", "source_config_hash": pv._canon_hash(cfg)}),
            encoding="utf-8",
        )
        # ripgrep.exe deliberately NOT created - simulates manual deletion

        def fake_download(url, dest_path):
            with zipfile.ZipFile(dest_path, "w") as zf:
                zf.writestr("ripgrep.exe", b"reinstalled")

        monkeypatch.setattr(pv, "_secure_download", fake_download)

        res = pv.ensure_tool("ripgrep", sys_dir=sys_dir)

        assert res["status"] == "success"
        assert (dest_dir / "ripgrep.exe").read_bytes() == b"reinstalled"

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
        monkeypatch.setattr(pv, "ensure_tool", lambda name, orch=None, sys_dir=None, force=False: calls.append(name) or {"status": "success"})

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
        monkeypatch.setattr(pv, "ensure_tool", lambda name, orch=None, sys_dir=None, force=False: calls.append(name) or {"status": "success"})

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
        tool_cfg = {
            "version": "2.1.206",
            "discovery_id": "@anthropic-ai/claude-code",
            "install_mechanism": "npm_peer",
        }
        sys_dir = _make_sys_dir(
            tmp_path,
            tools={"claude": tool_cfg},
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
            json.dumps({"declared_version": "2.1.206", "source_config_hash": pv._canon_hash(tool_cfg)}),
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


class TestDeferredDrainDispatch:
    def test_lazy_drain_processes_and_clears_queue(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {})
        pv._add_deferred(sys_dir, "ripgrep", "tool")

        calls = []
        monkeypatch.setattr(pv, "ensure_tool", lambda name, orch=None, sys_dir=None, force=False: calls.append(name))

        pv._drain_deferred_lazy(None, sys_dir)

        assert calls == ["ripgrep"]
        assert pv._load_deferred(sys_dir) == {}

    def test_lazy_drain_dispatches_runtime_kind(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {})
        pv._add_deferred(sys_dir, "nodejs", "runtime")

        calls = []
        monkeypatch.setattr(pv, "ensure_runtime", lambda name, orch=None, sys_dir=None, force=False: calls.append(name))

        pv._drain_deferred_lazy(None, sys_dir)

        assert calls == ["nodejs"]
        assert pv._load_deferred(sys_dir) == {}


class TestEnsureRuntime:
    def test_python_matches_running_interpreter_is_already_current(self, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {})
        running_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        (sys_dir / "runtimes.json").write_text(json.dumps({
            "runtimes": {"python": {"version": running_version, "url": "https://example/python.zip"}},
            "tools": {},
        }), encoding="utf-8")

        res = pv.ensure_runtime("python", sys_dir=sys_dir)

        assert res["status"] == "already_current"
        manifest = json.loads((sys_dir / "env" / "python" / ".install_manifest.json").read_text(encoding="utf-8"))
        assert manifest["declared_version"] == running_version

    def test_python_version_mismatch_errors_without_touching_disk(self, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {})
        (sys_dir / "runtimes.json").write_text(json.dumps({
            "runtimes": {"python": {"version": "99.99.99", "url": "https://example/python.zip"}},
            "tools": {},
        }), encoding="utf-8")

        res = pv.ensure_runtime("python", sys_dir=sys_dir)

        assert res["status"] == "error"
        assert "mismatch" in res["detail"]
        assert not (sys_dir / "env" / "python").exists()

    def test_preserve_tree_strip_components_1_unwraps_nodejs_style_zip(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {})
        (sys_dir / "runtimes.json").write_text(json.dumps({
            "runtimes": {"nodejs": {
                "version": "22.22.3",
                "url": "https://example/node.zip",
                "install_mechanism": "zip_tool",
                "archive_layout": "preserve_tree",
                "strip_components": 1,
            }},
            "tools": {},
        }), encoding="utf-8")

        def fake_download(url, dest_path):
            with zipfile.ZipFile(dest_path, "w") as zf:
                zf.writestr("node-v22.22.3-win-x64/node.exe", b"fake node")
                zf.writestr("node-v22.22.3-win-x64/node_modules/npm/package.json", b"{}")

        monkeypatch.setattr(pv, "_secure_download", fake_download)

        res = pv.ensure_runtime("nodejs", sys_dir=sys_dir)

        assert res["status"] == "success"
        dest_dir = sys_dir / "env" / "nodejs"
        assert (dest_dir / "node.exe").read_bytes() == b"fake node"
        assert (dest_dir / "node_modules" / "npm" / "package.json").exists()

    def test_preserve_tree_strip_components_0_keeps_flat_layout(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {})
        (sys_dir / "runtimes.json").write_text(json.dumps({
            "runtimes": {"vscode": {
                "version": "1.100.2",
                "url": "https://example/vscode.zip",
                "install_mechanism": "zip_tool",
                "archive_layout": "preserve_tree",
                "strip_components": 0,
            }},
            "tools": {},
        }), encoding="utf-8")

        def fake_download(url, dest_path):
            with zipfile.ZipFile(dest_path, "w") as zf:
                zf.writestr("Code.exe", b"fake code")
                zf.writestr("resources/app/package.json", b"{}")

        monkeypatch.setattr(pv, "_secure_download", fake_download)

        res = pv.ensure_runtime("vscode", sys_dir=sys_dir)

        assert res["status"] == "success"
        dest_dir = sys_dir / "env" / "vscode"
        assert (dest_dir / "Code.exe").read_bytes() == b"fake code"
        assert (dest_dir / "resources" / "app" / "package.json").exists()

    def test_sfx_exe_mechanism_runs_installer_with_o_and_y_flags(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {})
        (sys_dir / "runtimes.json").write_text(json.dumps({
            "runtimes": {"git": {
                "version": "2.49.0",
                "url": "https://example/PortableGit.7z.exe",
                "install_mechanism": "sfx_exe",
            }},
            "tools": {},
        }), encoding="utf-8")

        def fake_download(url, dest_path):
            dest_path.write_bytes(b"fake sfx installer")

        sfx_calls = []

        def fake_run(argv, **kwargs):
            sfx_calls.append(argv)
            dest_arg = argv[1]
            assert dest_arg.startswith("-o")
            assert argv[2] == "-y"
            dest_path = Path(dest_arg[2:])
            (dest_path / "cmd").mkdir(parents=True, exist_ok=True)
            (dest_path / "cmd" / "git.exe").write_bytes(b"fake git")
            return type("Completed", (), {"returncode": 0})()

        monkeypatch.setattr(pv, "_secure_download", fake_download)
        monkeypatch.setattr(pv.subprocess, "run", fake_run)

        res = pv.ensure_runtime("git", sys_dir=sys_dir)

        assert res["status"] == "success"
        assert len(sfx_calls) == 1
        assert (sys_dir / "env" / "git" / "cmd" / "git.exe").read_bytes() == b"fake git"

    def test_force_bypasses_already_current(self, monkeypatch, tmp_path):
        cfg = {"version": "22.22.3", "url": "https://example/node.zip", "archive_layout": "preserve_tree", "strip_components": 1}
        sys_dir = _make_sys_dir(tmp_path, {})
        (sys_dir / "runtimes.json").write_text(json.dumps({"runtimes": {"nodejs": cfg}, "tools": {}}), encoding="utf-8")

        dest_dir = sys_dir / "env" / "nodejs"
        dest_dir.mkdir(parents=True)
        (dest_dir / "node.exe").write_bytes(b"old node")
        (dest_dir / ".install_manifest.json").write_text(
            json.dumps({"declared_version": "22.22.3", "source_config_hash": pv._canon_hash({**cfg, "install_mechanism": "zip_tool", "preserve_paths": ["npm-global"]})}),
            encoding="utf-8",
        )

        downloads = []

        def fake_download(url, dest_path):
            downloads.append(url)
            with zipfile.ZipFile(dest_path, "w") as zf:
                zf.writestr("node-v22.22.3-win-x64/node.exe", b"new node")

        monkeypatch.setattr(pv, "_secure_download", fake_download)

        res_skip = pv.ensure_runtime("nodejs", sys_dir=sys_dir, force=False)
        assert res_skip["status"] == "already_current"
        assert downloads == []

        res_force = pv.ensure_runtime("nodejs", sys_dir=sys_dir, force=True)
        assert res_force["status"] == "success"
        assert downloads == [cfg["url"]]
        assert (dest_dir / "node.exe").read_bytes() == b"new node"

    def test_unknown_runtime_errors(self, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {})
        res = pv.ensure_runtime("nonexistent", sys_dir=sys_dir)
        assert res["status"] == "error"


class TestPreservePathsMigration:
    def test_nodejs_update_preserves_npm_global(self, monkeypatch, tmp_path):
        """The critical D11 fix: a routine nodejs version bump must not
        destroy npm-global (where claude/codex actually live)."""
        sys_dir = _make_sys_dir(tmp_path, {})
        (sys_dir / "runtimes.json").write_text(json.dumps({
            "runtimes": {"nodejs": {
                "version": "22.22.4",
                "url": "https://example/node-new.zip",
                "install_mechanism": "zip_tool",
                "archive_layout": "preserve_tree",
                "strip_components": 1,
                "preserve_paths": ["npm-global"],
            }},
            "tools": {},
        }), encoding="utf-8")

        old_dir = sys_dir / "env" / "nodejs"
        old_dir.mkdir(parents=True)
        (old_dir / "node.exe").write_bytes(b"old node")
        npm_global = old_dir / "npm-global"
        npm_global.mkdir()
        (npm_global / "claude.cmd").write_text("@echo off\n", encoding="utf-8")
        (old_dir / ".install_manifest.json").write_text(
            json.dumps({"declared_version": "22.22.3", "source_config_hash": "stale"}), encoding="utf-8"
        )

        def fake_download(url, dest_path):
            with zipfile.ZipFile(dest_path, "w") as zf:
                zf.writestr("node-v22.22.4-win-x64/node.exe", b"new node")

        monkeypatch.setattr(pv, "_secure_download", fake_download)

        res = pv.ensure_runtime("nodejs", sys_dir=sys_dir)

        assert res["status"] == "success"
        new_dir = sys_dir / "env" / "nodejs"
        assert (new_dir / "node.exe").read_bytes() == b"new node"
        assert (new_dir / "npm-global" / "claude.cmd").exists(), "npm-global (installed peer CLIs) must survive the swap"


class TestLeaseGate:
    def test_is_peer_leased_true_for_open_unexpired_lease(self, tmp_path):
        sys_dir = tmp_path / "_sys"
        sys_dir.mkdir()
        ai_dir = tmp_path / ".ai"
        ai_dir.mkdir()
        future = (pv.datetime.datetime.now() + pv.datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        (ai_dir / "leases.json").write_text(json.dumps({
            "cx": {"status": "open", "expires_at": future, "pid": 123}
        }), encoding="utf-8")

        assert pv._is_peer_leased(sys_dir, "cx") is True
        assert pv._is_peer_leased(sys_dir, "claude") is False

    def test_is_peer_leased_false_for_expired_lease(self, tmp_path):
        sys_dir = tmp_path / "_sys"
        sys_dir.mkdir()
        ai_dir = tmp_path / ".ai"
        ai_dir.mkdir()
        past = (pv.datetime.datetime.now() - pv.datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        (ai_dir / "leases.json").write_text(json.dumps({
            "cx": {"status": "open", "expires_at": past}
        }), encoding="utf-8")

        assert pv._is_peer_leased(sys_dir, "cx") is False

    def test_is_peer_leased_false_when_closed(self, tmp_path):
        sys_dir = tmp_path / "_sys"
        sys_dir.mkdir()
        ai_dir = tmp_path / ".ai"
        ai_dir.mkdir()
        future = (pv.datetime.datetime.now() + pv.datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        (ai_dir / "leases.json").write_text(json.dumps({
            "cx": {"status": "closed", "expires_at": future}
        }), encoding="utf-8")

        assert pv._is_peer_leased(sys_dir, "cx") is False

    def test_is_peer_leased_false_when_no_leases_file(self, tmp_path):
        sys_dir = tmp_path / "_sys"
        sys_dir.mkdir()
        assert pv._is_peer_leased(sys_dir, "cx") is False

    def test_nodejs_swap_deferred_when_any_peer_leased(self, monkeypatch, tmp_path):
        sys_dir = _make_sys_dir(tmp_path, {})
        (sys_dir / "runtimes.json").write_text(json.dumps({
            "runtimes": {"nodejs": {"version": "22.22.3", "url": "https://example/node.zip"}},
            "tools": {},
        }), encoding="utf-8")
        ai_dir = tmp_path / ".ai"
        ai_dir.mkdir()
        future = (pv.datetime.datetime.now() + pv.datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        (ai_dir / "leases.json").write_text(json.dumps({
            "cx": {"status": "open", "expires_at": future}
        }), encoding="utf-8")

        downloads = []
        monkeypatch.setattr(pv, "_secure_download", lambda url, dest: downloads.append(url))

        res = pv.ensure_runtime("nodejs", sys_dir=sys_dir)

        assert res["status"] == "in_use_deferred"
        assert downloads == []
        assert pv._load_deferred(sys_dir) == {"runtime:nodejs": {"kind": "runtime", "name": "nodejs"}}


class TestNpmPeerCanaryAndRetry:
    def _base_setup(self, tmp_path, declared_version="2.1.206", canary=None):
        tool_cfg = {
            "version": declared_version,
            "discovery_id": "@anthropic-ai/claude-code",
            "install_mechanism": "npm_peer",
        }
        if canary:
            tool_cfg["canary"] = canary
        sys_dir = _make_sys_dir(
            tmp_path,
            tools={"claude": tool_cfg},
            peers={"claude": {"npm_package": "@anthropic-ai/claude-code", "node_ids": ["cc", "ca"]}},
        )
        node_exe = sys_dir / "env" / "nodejs" / "node.exe"
        node_exe.parent.mkdir(parents=True, exist_ok=True)
        node_exe.write_bytes(b"fake node")
        return sys_dir, tool_cfg

    def test_canary_runs_after_install_before_manifest_write(self, monkeypatch, tmp_path):
        sys_dir, _ = self._base_setup(tmp_path, canary={"argv": ["claude.cmd", "--version"], "expect_regex": "2\\.1\\.206"})

        npm_global = sys_dir / "env" / "nodejs" / "npm-global"

        def fake_run(argv, **kwargs):
            if "view" in argv:
                return type("R", (), {"stdout": '"sha512-fake"', "returncode": 0})()
            if "install" in argv:
                npm_global.mkdir(parents=True, exist_ok=True)
                (npm_global / "claude.cmd").write_text("@echo 2.1.206\n", encoding="utf-8")
                return type("R", (), {"returncode": 0})()
            if argv[0].endswith("claude.cmd"):
                return type("R", (), {"stdout": "2.1.206", "stderr": "", "returncode": 0})()
            raise AssertionError(f"unexpected call: {argv}")

        monkeypatch.setattr(pv.subprocess, "run", fake_run)

        res = pv.ensure_peer_cli("claude", sys_dir=sys_dir)

        assert res["status"] == "success"
        manifest = json.loads((sys_dir / "tools" / "claude" / ".install_manifest.json").read_text(encoding="utf-8"))
        assert manifest["canary_output"]

    def test_bootstrap_canary_failure_is_hard_error_no_manifest(self, monkeypatch, tmp_path):
        sys_dir, _ = self._base_setup(tmp_path, canary={"argv": ["claude.cmd", "--version"], "expect_regex": "NEVER_MATCHES"})

        npm_global = sys_dir / "env" / "nodejs" / "npm-global"

        def fake_run(argv, **kwargs):
            if "view" in argv:
                return type("R", (), {"stdout": '"sha512-fake"', "returncode": 0})()
            if "install" in argv:
                npm_global.mkdir(parents=True, exist_ok=True)
                (npm_global / "claude.cmd").write_text("@echo off\n", encoding="utf-8")
                return type("R", (), {"returncode": 0})()
            if argv[0].endswith("claude.cmd"):
                return type("R", (), {"stdout": "", "stderr": "", "returncode": 0})()
            raise AssertionError(f"unexpected call: {argv}")

        monkeypatch.setattr(pv.subprocess, "run", fake_run)

        res = pv.ensure_peer_cli("claude", sys_dir=sys_dir)

        assert res["status"] == "npm_canary_failed"
        assert not (sys_dir / "tools" / "claude" / ".install_manifest.json").exists()

    def test_update_canary_failure_rolls_back_to_old_version(self, monkeypatch, tmp_path):
        sys_dir, _tool_cfg = self._base_setup(tmp_path, declared_version="3.0.0", canary={"argv": ["claude.cmd", "--version"], "expect_regex": "\\d+\\.\\d+\\.\\d+"})

        manifest_dir = sys_dir / "tools" / "claude"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / ".install_manifest.json").write_text(
            json.dumps({"declared_version": "2.1.206", "source_config_hash": "irrelevant-old-hash"}), encoding="utf-8"
        )

        npm_global = sys_dir / "env" / "nodejs" / "npm-global"
        install_calls = []
        current_version = {"v": None}

        def fake_run(argv, **kwargs):
            if "view" in argv:
                return type("R", (), {"stdout": '"sha512-fake"', "returncode": 0})()
            if "install" in argv:
                pkg_at_version = argv[argv.index("install") + 2]
                install_calls.append(pkg_at_version)
                current_version["v"] = pkg_at_version.split("@")[-1]
                npm_global.mkdir(parents=True, exist_ok=True)
                (npm_global / "claude.cmd").write_text("@echo off\n", encoding="utf-8")
                return type("R", (), {"returncode": 0})()
            if argv[0].endswith("claude.cmd"):
                if current_version["v"] == "3.0.0":
                    # simulate a broken 3.0.0 build that fails its version check
                    return type("R", (), {"stdout": "", "stderr": "fatal error", "returncode": 1})()
                return type("R", (), {"stdout": current_version["v"], "stderr": "", "returncode": 0})()
            raise AssertionError(f"unexpected call: {argv}")

        monkeypatch.setattr(pv.subprocess, "run", fake_run)

        res = pv.ensure_peer_cli("claude", sys_dir=sys_dir)

        assert res["status"] == "error"
        assert "rolled back to 2.1.206" in res["detail"]
        assert install_calls == ["@anthropic-ai/claude-code@3.0.0", "@anthropic-ai/claude-code@2.1.206"]

    def test_npm_install_failure_classified_as_retry_deferred_not_lock_specific(self, monkeypatch, tmp_path):
        sys_dir, _ = self._base_setup(tmp_path)

        def fake_run(argv, **kwargs):
            if "view" in argv:
                return type("R", (), {"stdout": '"sha512-fake"', "returncode": 0})()
            if "install" in argv:
                raise pv.subprocess.CalledProcessError(1, argv)
            raise AssertionError(f"unexpected call: {argv}")

        monkeypatch.setattr(pv.subprocess, "run", fake_run)

        res = pv.ensure_peer_cli("claude", sys_dir=sys_dir)

        assert res["status"] == "npm_install_retry_deferred"
        deferred = pv._load_deferred(sys_dir)
        entry = deferred["peer:claude"]
        assert entry["attempts"] == 1
        assert entry["version"] == "2.1.206"
        assert entry["last_exit_code"] == 1

    def test_npm_install_hard_fails_after_max_retries(self, monkeypatch, tmp_path):
        sys_dir, _ = self._base_setup(tmp_path)

        def fake_run(argv, **kwargs):
            if "view" in argv:
                return type("R", (), {"stdout": '"sha512-fake"', "returncode": 0})()
            if "install" in argv:
                raise pv.subprocess.CalledProcessError(1, argv)
            raise AssertionError(f"unexpected call: {argv}")

        monkeypatch.setattr(pv.subprocess, "run", fake_run)

        for _ in range(pv.MAX_NPM_INSTALL_RETRIES - 1):
            res = pv.ensure_peer_cli("claude", sys_dir=sys_dir)
            assert res["status"] == "npm_install_retry_deferred"

        res_final = pv.ensure_peer_cli("claude", sys_dir=sys_dir)
        assert res_final["status"] == "npm_install_failed"

        # further calls short-circuit without even attempting npm view/install
        calls_after = []

        def fail_if_called(*a, **k):
            calls_after.append(a)
            raise AssertionError("should not be called")

        monkeypatch.setattr(pv.subprocess, "run", fail_if_called)
        res_blocked = pv.ensure_peer_cli("claude", sys_dir=sys_dir)
        assert res_blocked["status"] == "error"
        assert "npm_install_failed" in res_blocked["detail"]
        assert calls_after == []

    def test_declared_version_change_resets_retry_counter(self, monkeypatch, tmp_path):
        sys_dir, _ = self._base_setup(tmp_path, declared_version="2.1.206")

        def fake_run_fail(argv, **kwargs):
            if "view" in argv:
                return type("R", (), {"stdout": '"sha512-fake"', "returncode": 0})()
            if "install" in argv:
                raise pv.subprocess.CalledProcessError(1, argv)
            raise AssertionError(f"unexpected call: {argv}")

        monkeypatch.setattr(pv.subprocess, "run", fake_run_fail)
        for _ in range(pv.MAX_NPM_INSTALL_RETRIES):
            pv.ensure_peer_cli("claude", sys_dir=sys_dir)

        deferred = pv._load_deferred(sys_dir)
        assert deferred["peer:claude"]["attempts"] == pv.MAX_NPM_INSTALL_RETRIES

        # bump declared_version in runtimes.json - counter must reset
        raw = json.loads((sys_dir / "runtimes.json").read_text(encoding="utf-8"))
        raw["tools"]["claude"]["version"] = "2.2.0"
        (sys_dir / "runtimes.json").write_text(json.dumps(raw), encoding="utf-8")

        npm_global = sys_dir / "env" / "nodejs" / "npm-global"

        def fake_run_succeed(argv, **kwargs):
            if "view" in argv:
                return type("R", (), {"stdout": '"sha512-fake"', "returncode": 0})()
            if "install" in argv:
                npm_global.mkdir(parents=True, exist_ok=True)
                (npm_global / "claude.cmd").write_text("@echo off\n", encoding="utf-8")
                return type("R", (), {"returncode": 0})()
            raise AssertionError(f"unexpected call: {argv}")

        monkeypatch.setattr(pv.subprocess, "run", fake_run_succeed)
        res = pv.ensure_peer_cli("claude", sys_dir=sys_dir)
        assert res["status"] == "success"
