"""Glue-level guarantees of core.repair that the ag-drafted suite did not pin down
(placeholder URL/version, fictional package names, exit-code mapping, pin handling)."""
import json
import sys
from pathlib import Path

import pytest

from _sys.core.root import find_root

sys.path.insert(0, str(find_root(__file__)))
from core import env_ops, repair, python_manager  # noqa: E402



@pytest.fixture(autouse=True)
def mock_python_discovery(monkeypatch):
    from core import version_resolver
    monkeypatch.setattr(version_resolver, "resolve_latest",
                        lambda *a, **k: {"status": "error", "detail": "mock network unavailable"})


def _tree(tmp_path, pin_version="3.14.8", sha=None, installed=None):
    sys_dir = tmp_path / "_sys"
    (sys_dir / "data" / "state").mkdir(parents=True)
    py = {"version": pin_version, "url": f"https://www.python.org/ftp/python/{pin_version}/python-{pin_version}-embed-amd64.zip"}
    if sha:
        py["sha256"] = sha
    (sys_dir / "runtimes.json").write_text(json.dumps({"runtimes": {"python": py}}), encoding="utf-8")
    if installed:
        (sys_dir / "env" / "python").mkdir(parents=True)
        (sys_dir / "env" / "python" / "python.exe").write_text("x")
    return sys_dir


def _update(tmp_path, args, only, installed="3.14.8", **tree):
    sys_dir = _tree(tmp_path, installed=installed, **tree)
    def runner(argv, timeout):
        return (0, f"Python {installed}") if "--version" in argv else (0, "")
    # dry run: build the plan only
    captured = {}
    orig = repair._repair_engine_main

    ctx = {"sys_dir": sys_dir, "base_dir": tmp_path, "args": list(args), "command": "engram update"}
    import types
    res = repair.update_env_main(ctx, only) if False else None
    return sys_dir, runner


# ---- result mapping (design section 10 exit codes) -------------------------------------------------

@pytest.mark.parametrize("res,mode,code,status", [
    ({"status": "success", "phase": "COMMITTED", "detail": "ok"}, "apply", 0, "success"),
    ({"status": "failed", "phase": "ROLLED_BACK", "detail": "verify failed"}, "apply", 12, "failed"),
    ({"status": "failed", "phase": "ROLLBACK_FAILED", "detail": "undo failed"}, "apply", 13, "failed"),
    ({"status": "failed", "phase": None, "detail": "environment lock busy"}, "apply", 11, "failed"),
    ({"status": "failed", "phase": None, "detail": "non-terminal journal blocks"}, "apply", 14, "failed"),
    ({"status": "failed", "phase": "ROLLED_BACK", "detail": "x"}, "rollback", 0, "success"),
    ({"status": "failed", "phase": "ROLLBACK_FAILED", "detail": "x"}, "rollback", 13, "failed"),
    ({"status": "success", "phase": "COMMITTED", "detail": "x"}, "resume", 0, "success"),
    ({"status": "failed", "phase": "ROLLED_BACK", "detail": "x"}, "resume", 12, "failed"),
])
def test_cli_result_mapping(res, mode, code, status):
    out = repair._cli_result(res, mode=mode)
    assert out["exit_code"] == code and out["status"] == status and out["operation"] == "repair"


# ---- python pin / installed version ----------------------------------------------------------------------

def test_python_pin_is_read_from_runtimes_json(tmp_path):
    sys_dir = _tree(tmp_path, pin_version="3.14.9", sha="ab" * 32)
    pin = repair._python_pin(sys_dir)
    assert pin["version"] == "3.14.9" and pin["sha256"] == "ab" * 32
    assert pin["url"].endswith("python-3.14.9-embed-amd64.zip")


def test_missing_runtimes_json_gives_an_empty_pin(tmp_path):
    assert repair._python_pin(tmp_path / "nope") == {"version": "", "url": "", "sha256": None}


def test_installed_python_prefers_the_manifest(tmp_path):
    from core import env_manifest
    sys_dir = _tree(tmp_path)
    env_manifest.write_manifest(sys_dir, {"schema_version": 1, "install_id": "i" * 36,
                                          "root": {"logical": "x", "physical": "x"},
                                          "python": {"version": "3.14.7"}})
    assert repair._installed_python(sys_dir, {"runner": lambda a, t: (0, "Python 9.9.9")}) == "3.14.7"


def test_installed_python_falls_back_to_probing_the_interpreter(tmp_path):
    sys_dir = _tree(tmp_path, installed="3.14.8")
    assert repair._installed_python(sys_dir, {"runner": lambda a, t: (0, "Python 3.14.8\n")}) == "3.14.8"


def test_installed_python_absent_is_none(tmp_path):
    assert repair._installed_python(_tree(tmp_path), {}) is None


# ---- update plan: no placeholders ---------------------------------------------------------------------------

def _plan(tmp_path, args, only, installed="3.14.8", **tree):
    sys_dir = _tree(tmp_path, installed=installed, **tree)
    ctx = {"sys_dir": sys_dir, "base_dir": tmp_path, "args": list(args), "command": "engram update"}
    out = repair.update_env_main(ctx, set(only))
    return out


def test_update_python_dry_run_uses_the_pin_not_a_placeholder(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(repair, "_installed_python", lambda s, seams: "3.14.7")
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {"manifest": "ok", "drift": {"status": "consistent"},
                                                           "findings": [], "stale_registry": [], "journal": None, "lock": None})
    out = _plan(tmp_path, [], {"python"}, pin_version="3.14.8")
    text = capsys.readouterr().out
    assert out["exit_code"] == 0 and "example.com" not in text
    assert "3.14.7 -> 3.14.8" in text and "patch" in text


def test_update_python_to_a_major_version_is_blocked_without_the_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(repair, "_installed_python", lambda s, seams: "3.14.8")
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {"manifest": "ok", "drift": {"status": "consistent"},
                                                           "findings": [], "stale_registry": [], "journal": None, "lock": None})
    out = _plan(tmp_path, ["--to", "4.0.0"], {"python"})
    assert out["exit_code"] != 0 and "allow-major-runtime-upgrade" in out["detail"]


def test_update_python_same_version_is_a_noop_unless_forced(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(repair, "_installed_python", lambda s, seams: "3.14.8")
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {"manifest": "ok", "drift": {"status": "consistent"},
                                                           "findings": [], "stale_registry": [], "journal": None, "lock": None})
    out = _plan(tmp_path, [], {"python"})
    assert out["exit_code"] == 0 and "already at 3.14.8" in capsys.readouterr().out


# ---- packages: real names, venv interpreter, snapshot first -------------------------------------------------------

def test_package_upgrade_steps_use_real_baseline_names_and_the_venv_python(tmp_path):
    sys_dir = _tree(tmp_path)
    calls = []
    steps = repair.steps_from_spec(sys_dir, tmp_path, [{"name": "upgrade-packages", "group": "A", "kind": "packages",
                                                       "params": {"all_packages": False}}],
                                   runner=lambda argv, t: calls.append(argv) or (0, ""))
    assert [s.name for s in steps] == ["snapshot-packages", "upgrade-packages"]
    ctx = env_ops.OpContext(sys_dir, "op", "update", {}, {})
    steps[1].do(ctx)
    argv = calls[0]
    assert argv[0].endswith("python.exe") and "venv" in argv[0]
    assert argv[1:5] == ["-m", "pip", "install", "--upgrade"]
    assert set(argv[5:]) == {"filelock", "psutil", "pydantic", "pywinpty"}
    assert not any("engram" in a for a in argv)


def test_all_packages_adds_requested_non_editable_packages(tmp_path):
    from core import venv_manager
    sys_dir = _tree(tmp_path)
    venv_manager.write_snapshot(sys_dir, {"created_at": "2026-10-02T00:00:00Z", "packages": [
        {"name": "pytest", "requested": True, "editable": False},
        {"name": "peerhub", "requested": True, "editable": True},
        {"name": "pluggy", "requested": False, "editable": False},
        {"name": "psutil", "requested": True, "editable": False}]})
    calls = []
    steps = repair.steps_from_spec(sys_dir, tmp_path, [{"name": "upgrade-packages", "group": "A", "kind": "packages",
                                                       "params": {"all_packages": True}}],
                                   runner=lambda argv, t: calls.append(argv) or (0, ""))
    steps[1].do(env_ops.OpContext(sys_dir, "op", "update", {}, {}))
    names = set(calls[0][5:])
    assert "pytest" in names and "peerhub" not in names and "pluggy" not in names
    assert {"filelock", "psutil", "pydantic", "pywinpty"} <= names


def test_package_upgrade_failure_raises_so_the_engine_reports_it(tmp_path):
    sys_dir = _tree(tmp_path)
    steps = repair.steps_from_spec(sys_dir, tmp_path, [{"name": "upgrade-packages", "group": "A", "kind": "packages",
                                                       "params": {}}], runner=lambda argv, t: (1, "boom"))
    with pytest.raises(RuntimeError, match="pip upgrade failed"):
        steps[1].do(env_ops.OpContext(sys_dir, "op", "update", {}, {}))


# ---- adoption is group B and idempotent -------------------------------------------------------------------------

def test_adopt_manifest_describes_the_current_root_and_records_last_base_dir(tmp_path):
    from core import env_manifest
    sys_dir = _tree(tmp_path)
    steps = repair.steps_from_spec(sys_dir, tmp_path, [{"name": "adopt-manifest", "group": "B", "kind": "manifest", "params": {}}])
    assert steps[0].group == "B"
    steps[0].do(env_ops.OpContext(sys_dir, "op", "repair", {}, {}))
    data = env_manifest.read_manifest(sys_dir).data
    assert data["root"]["logical"] == str(tmp_path)
    assert (sys_dir / "data" / "last_base_dir.txt").read_text(encoding="utf-8") == str(tmp_path)
    assert steps[0].done(env_ops.OpContext(sys_dir, "op", "repair", {}, {})) is True


# ---- new plan persist tests ------------------------------------------------------------------------------------

def test_update_spec_contains_installed_and_had_venv(tmp_path, monkeypatch):
    monkeypatch.setattr(repair, "_installed_python", lambda s, seams: "3.14.7")
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {"manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "stale_registry": [], "journal": None, "lock": None})
    sys_dir = _tree(tmp_path, pin_version="3.14.8")
    (sys_dir / "env" / "venv" / "Scripts").mkdir(parents=True)
    (sys_dir / "env" / "venv" / "Scripts" / "python.exe").write_text("")
    
    captured_spec = []
    original = repair.steps_from_spec
    def spy_steps(s, b, spec, **seams):
        captured_spec.extend(spec)
        return original(s, b, spec, **seams)
    
    monkeypatch.setattr(repair, "steps_from_spec", spy_steps)
    ctx = {"sys_dir": sys_dir, "base_dir": tmp_path, "args": [], "command": "engram update"}
    repair.update_env_main(ctx, {"python"})
    
    assert len(captured_spec) == 1
    assert captured_spec[0]["params"]["installed"] == "3.14.7"
    assert captured_spec[0]["params"]["had_venv"] is True

def test_steps_from_spec_forwards_installed_and_had_venv(tmp_path, monkeypatch):
    sys_dir = _tree(tmp_path)
    spec = [{
        "name": "update-python", "group": "A", "kind": "python",
        "params": {"target_version": "3.14.9", "url": "x", "installed": "3.14.7", "had_venv": True}
    }]
    
    captured_kwargs = {}
    def fake_plan(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return []
    
    monkeypatch.setattr(python_manager, "plan_python_update", fake_plan)
    repair.steps_from_spec(sys_dir, tmp_path, spec)
    assert captured_kwargs.get("installed") == "3.14.7"
    assert captured_kwargs.get("had_venv") is True

def test_steps_from_spec_without_installed_had_venv_works(tmp_path, monkeypatch):
    sys_dir = _tree(tmp_path)
    spec = [{
        "name": "update-python", "group": "A", "kind": "python",
        "params": {"target_version": "3.14.9", "url": "x"}
    }]
    
    captured_kwargs = {}
    def fake_plan(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return []
    
    monkeypatch.setattr(python_manager, "plan_python_update", fake_plan)
    repair.steps_from_spec(sys_dir, tmp_path, spec)
    assert captured_kwargs.get("installed") is None
    assert captured_kwargs.get("had_venv") is None


def _discovery(monkeypatch, patches=None):
    from core import version_resolver
    calls = []
    def resolve(*args, **kwargs):
        calls.append(kwargs)
        return {"status": "ok", "latest_version": "3.15.2", "latest_minor_cycle": "3.15",
                "latest_patch_by_cycle": patches or {"3.14": "3.14.9", "3.15": "3.15.2"}}
    monkeypatch.setattr(version_resolver, "resolve_latest", resolve)
    return calls


@pytest.mark.parametrize("pin", ["3.14.7", "3.15.2"])
def test_default_target_is_latest_installed_minor_patch(tmp_path, monkeypatch, pin):
    _discovery(monkeypatch)
    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.14.8")
    result = _plan(tmp_path, [], {"python"}, pin_version=pin)
    params = result["plan"]["spec"][0]["params"]
    assert params["target_version"] == "3.14.9"
    assert params["sha256"] is None
    summary = "\n".join(result["plan"]["summary"])
    assert "3.14.8 / " + pin + " / 3.14.9 / 3.15 (3.15.2)" in summary
    assert "engram update --only python --yes" in summary
    assert "engram update --only python --to 3.15.2 --yes" in summary
    assert "downloaded over HTTPS from python.org; no pinned SHA-256" in summary


@pytest.mark.parametrize("pin", ["3.14.7", "3.15.2"])
def test_failed_discovery_never_downgrades_or_crosses_minor(tmp_path, monkeypatch, pin):
    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.14.8")
    result = _plan(tmp_path, [], {"python"}, pin_version=pin)
    assert result["plan"]["spec"] == []
    assert "falling back to pin" in "\n".join(result["plan"]["summary"])
    assert "Keeping Python 3.14.8" in "\n".join(result["plan"]["summary"])


def test_offline_falls_back_to_pin_without_fetching(tmp_path, monkeypatch):
    from core import version_resolver
    def unexpected(*args, **kwargs):
        raise AssertionError("network must not run")
    monkeypatch.setattr(version_resolver, "resolve_latest", unexpected)
    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.14.7")
    result = _plan(tmp_path, ["--offline"], {"python"})
    assert result["plan"]["spec"][0]["params"]["target_version"] == "3.14.8"
    assert "offline mode" in "\n".join(result["plan"]["summary"])


def test_refresh_is_forwarded_through_update_dispatch(tmp_path, monkeypatch):
    from core import updater
    calls = _discovery(monkeypatch)
    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.14.8")
    result = _plan(tmp_path, updater._env_update_args(["--only", "python", "--refresh", "--check"]),
                   {"python"})
    assert result["exit_code"] == 0 and calls[0]["force_refresh"] is True


def _wheel(filename, **kwargs):
    return {"filename": filename, **kwargs}


def test_minor_preflight_accepts_target_tag_and_older_abi3():
    calls = []
    def fetch(url, *, method="GET"):
        calls.append((url, method))
        if method == "HEAD":
            return None
        tag = "cp314-cp314" if "/pywinpty/" in url else "cp39-abi3"
        return {"releases": {"1.0.0": [_wheel(f"pkg-1.0.0-{tag}-win_amd64.whl")]}}
    assert repair._python_minor_preflight("3.14.8", "https://www.python.org/embed.zip", fetch=fetch) == []
    assert calls[0][1] == "HEAD"
    assert [url for url, method in calls[1:]] == [
        f"https://pypi.org/pypi/{package}/json" for package in ("pywinpty", "pydantic-core", "psutil")]


@pytest.mark.parametrize("filename", [
    "pkg-1.0.0-cp313-cp313-win_amd64.whl",
    "pkg-1.0.0-cp315-abi3-win_amd64.whl",
    "pkg-1.0.0-cp314-cp314-win_arm64.whl",
    "pkg-1.0.0-py3-none-any.whl",
])
def test_minor_preflight_rejects_incompatible_wheels(filename):
    def fetch(url, *, method="GET"):
        return None if method == "HEAD" else {"releases": {"1.0.0": [_wheel(filename)]}}
    missing = repair._python_minor_preflight("3.14.8", "embed", fetch=fetch)
    assert len(missing) == 3 and all("cp314" in item for item in missing)


def test_minor_preflight_lists_all_fetch_failures():
    def fail(url, *, method="GET"):
        raise OSError("mock offline")
    missing = repair._python_minor_preflight("3.14.8", "embed", fetch=fail)
    assert len(missing) == 4
    assert all(any(name in item for item in missing)
               for name in ("embed zip", "pywinpty", "pydantic-core", "psutil"))


@pytest.mark.parametrize("force", [False, True])
def test_minor_jump_requires_preflight_unless_forced(tmp_path, monkeypatch, force):
    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.14.8")
    monkeypatch.setattr(repair, "_python_fetch", lambda *a, **k: {"releases": {}})
    args = ["--to", "3.15.2"] + (["--force"] if force else [])
    result = _plan(tmp_path, args, {"python"})
    if force:
        params = result["plan"]["spec"][0]["params"]
        assert params["target_version"] == "3.15.2" and params["force"] is True
        assert "--force overrides" in "\n".join(result["plan"]["summary"])
    else:
        assert result["exit_code"] == 11
        assert "pywinpty" in result["detail"] and "Use --force" in result["detail"]


@pytest.mark.parametrize("cached", [False, True])
def test_unpinned_download_records_hash_and_warning(tmp_path, capsys, cached):
    from core import provisioner
    sys_dir = _tree(tmp_path)
    archive, checksum = python_manager.cache_paths(sys_dir, "3.14.9")
    if cached:
        archive.parent.mkdir(parents=True)
        archive.write_bytes(b"mock archive")
        checksum.write_text(provisioner._hash_file(archive, "sha256"))
    calls = []
    def download(url, destination):
        calls.append(url)
        destination.write_bytes(b"mock archive")
    steps = python_manager.plan_python_update(
        sys_dir, "3.14.9", url="https://www.python.org/embed.zip",
        installed="3.14.8", downloader=download)
    ctx = env_ops.OpContext(sys_dir, "hash-test", "update", {}, {})
    next(step for step in steps if "download" in step.name).do(ctx)
    actual = provisioner._hash_file(archive, "sha256")
    assert ctx.data["python_download_sha256"] == actual == checksum.read_text()
    assert bool(calls) is not cached
    output = capsys.readouterr().out
    assert actual in output and "downloaded over HTTPS from python.org; no pinned SHA-256" in output
