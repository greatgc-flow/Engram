"""Glue-level guarantees of core.repair that the ag-drafted suite did not pin down
(placeholder URL/version, fictional package names, exit-code mapping, pin handling)."""
import json
import subprocess
import urllib.error
from types import SimpleNamespace
import sys
from pathlib import Path

import pytest

from _sys.core.root import find_root

sys.path.insert(0, str(find_root(__file__)))
from core import env_ops, repair, python_manager  # noqa: E402



@pytest.fixture(autouse=True)
def mock_python_discovery(monkeypatch):
    monkeypatch.setattr(repair.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(repair, "_python_fetch", lambda *a, **k: None)
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
    monkeypatch.setattr(repair, "_minor_readiness", lambda s, target, url, **k:
                        repair.PythonReadiness(target, url, (), "ok"))
    _discovery(monkeypatch)
    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.14.8")
    result = _plan(tmp_path, [], {"python"}, pin_version=pin)
    params = result["plan"]["spec"][0]["params"]
    assert params["target_version"] == "3.14.9"
    assert params["sha256"] is None
    summary = "\n".join(result["plan"]["summary"])
    assert "3.14.8 / " + pin + " / 3.14.9 / 3.15 (3.15.2)" in summary
    assert "engram update -o python -y" in summary
    assert "engram update -o python --latest -y" in summary
    assert ("Python 3.15 dependency readiness verified.\n"
            "  Next: engram update -o python --latest -y") in summary
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
    monkeypatch.setattr(repair, "_minor_readiness", lambda s, target, url, **k:
                        repair.PythonReadiness(target, url, (), "ok"))
    from core import updater
    calls = _discovery(monkeypatch)
    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.14.8")
    result = _plan(tmp_path, updater._env_update_args(["--only", "python", "--refresh", "--check"]),
                   {"python"})
    assert result["exit_code"] == 0 and calls[0]["force_refresh"] is True


def _resolve(target="3.15.2", *, code=0, output="", fetch=None, run=None):
    return repair._python_minor_preflight(
        target, "embed", managed_python=Path("managed/python.exe"),
        specs=("filelock", "psutil==7.0", "pydantic", "pywinpty"),
        fetch=fetch or (lambda *a, **k: None),
        run=run or (lambda *a, **k: SimpleNamespace(returncode=code, stdout="", stderr=output)))


def test_minor_preflight_resolves_target_patch_and_complete_baseline_once():
    heads, calls = [], []
    def fetch(url, *, method):
        heads.append((url, method))
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="Would install baseline", stderr="")
    result = _resolve(fetch=fetch, run=run)
    assert result.state == "ok" and not result.reason
    assert heads == [("embed", "HEAD")] and len(calls) == 1
    argv, options = calls[0]
    assert argv[:4] == [str(Path("managed/python.exe")), "-m", "pip", "install"]
    assert "--dry-run" in argv and "--ignore-installed" in argv
    assert "--only-binary=:all:" in argv
    assert argv[argv.index("--python-version") + 1] == "3.15.2"
    assert argv[argv.index("--abi") + 1] == "cp315"
    assert argv[argv.index("--platform") + 1] == "win_amd64"
    assert argv[argv.index("--implementation") + 1] == "cp"
    assert tuple(argv[-4:]) == result.specs
    assert options["timeout"] == 120


@pytest.mark.parametrize("output", [
    "ERROR: ResolutionImpossible: conflicting dependencies",
    "ERROR: No matching distribution found for pywinpty",
    "ERROR: Package 'psutil' requires a different Python: 3.15.2 not in '<3.15'",
    "Ignored the following versions that require a different python version: "
    "1.0 Requires-Python <3.15; ERROR: Could not find a version that satisfies the requirement pydantic",
])
def test_minor_preflight_dependency_and_requires_python_exclusion_block(output):
    result = _resolve(code=1, output=output)
    assert result.state == "blocked"
    assert result.reason == "no compatible dependency set"


@pytest.mark.parametrize("output", [
    "WARNING: Retrying after connection broken\nERROR: No matching distribution found for psutil",
    "ERROR: Could not fetch URL: 503 Server Error",
    "No module named pip",
    "no such option: --dry-run",
    "unexpected resolver error",
    "Ignored versions that require a different Python: <3.15\nERROR: unexpected resolver error",
])
def test_minor_preflight_network_and_tool_failures_are_unverifiable(output):
    assert _resolve(code=1, output=output).state == "unverifiable"


@pytest.mark.parametrize("failure", [
    OSError("network unavailable"),
    subprocess.TimeoutExpired(["pip"], 120),
])
def test_minor_preflight_subprocess_failures_are_unverifiable(failure):
    def run(*a, **k):
        raise failure
    assert _resolve(run=run).state == "unverifiable"


@pytest.mark.parametrize("code,state", [(404, "blocked"), (410, "blocked"), (503, "unverifiable")])
def test_minor_preflight_archive_http_failure_skips_pip(code, state):
    def fetch(url, **k):
        raise urllib.error.HTTPError(url, code, "failure", {}, None)
    def run(*a, **k):
        pytest.fail("archive failure must skip pip")
    assert _resolve(fetch=fetch, run=run).state == state


def test_minor_preflight_archive_network_failure_skips_pip():
    def fetch(*a, **k):
        raise OSError("offline")
    def run(*a, **k):
        pytest.fail("archive failure must skip pip")
    assert _resolve(fetch=fetch, run=run).state == "unverifiable"


def test_minor_preflight_pip_can_exclude_versions_and_still_resolve():
    result = _resolve(output="Ignored versions that require a different Python: <3.15\nWould install pydantic")
    assert result.state == "ok"


def test_minor_preflight_success_after_network_retry_is_verified():
    assert _resolve(output="WARNING: Retrying connection\nWould install baseline").state == "ok"


def test_minor_preflight_normalizes_tool_failure_reason():
    result = _resolve(code=1, output="broken tool\n\uac00 " + "x" * 300)
    assert result.state == "unverifiable"
    assert result.reason.isascii() and "\n" not in result.reason
    assert "\\uac00" in result.reason and len(result.reason) == 240


def test_readiness_status_remains_json_serializable():
    readiness = _resolve()
    assert json.loads(json.dumps({"readiness": readiness}))["readiness"][3] == "ok"


@pytest.mark.parametrize("code,output,state", [
    (0, "", "ok"),
    (1, "ERROR: ResolutionImpossible", "blocked"),
    (1, "No module named pip", "unverifiable"),
])
def test_minor_readiness_shared_by_status_and_guard_once_per_plan(monkeypatch, code, output, state):
    heads, calls, statuses = [], [], []
    sys_dir = Path("unused-managed-tree")
    monkeypatch.setattr(repair, "_python_pin", lambda *a:
                        {"version": "3.14.8", "url": "", "sha256": None})
    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.14.8")
    monkeypatch.setattr(repair.venv_manager, "build_snapshot", lambda *a, **k: {
        "packages": [{"name": "psutil", "version": "7.0"}]})
    monkeypatch.setattr(repair, "steps_from_spec", lambda *a, **k: [])
    original_status = repair.python_update_status
    def status(*a, **k):
        result = original_status(*a, **k)
        statuses.append(result)
        return result
    monkeypatch.setattr(repair, "python_update_status", status)
    def run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=code, stdout="", stderr=output)
    seams = {
        "resolve_python": lambda *a, **k: {
            "status": "ok", "latest_version": "3.15.2", "latest_minor_cycle": "3.15",
            "latest_patch_by_cycle": {"3.14": "3.14.9"}},
        "fetch": lambda url, **k: heads.append((url, k["method"])),
        "resolver_run": run,
    }
    def engine(ctx, builder, setup):
        args = SimpleNamespace(to_version=None, latest=True, offline=False,
                               refresh=False, force=False, allow_major_runtime_upgrade=False)
        return builder(sys_dir, sys_dir.parent, {}, cli_args=args, seams=seams)
    monkeypatch.setattr(repair, "_repair_engine_main", engine)
    # A later invocation must check again; no process/global cache.
    for invocation in range(2):
        if state == "ok":
            plan = repair.update_env_main({}, {"python"})
            assert plan["spec"][0]["params"]["target_version"] == "3.15.2"
        else:
            with pytest.raises(ValueError, match=f"pre-flight {state}"):
                repair.update_env_main({}, {"python"})
        readiness = statuses[-1]["readiness"]
        assert readiness.state == state
        assert ("engram update -o python --latest -y" in statuses[-1]["commands"]) == (state == "ok")
        assert "psutil==7.0" in readiness.specs
        assert tuple(calls[-1][-len(readiness.specs):]) == readiness.specs
        assert len(heads) == len(calls) == invocation + 1


def test_minor_readiness_offline_does_not_fetch_or_resolve(monkeypatch):
    def unexpected(*a, **k):
        pytest.fail("offline readiness must not access network or pip")
    result = repair._minor_readiness(Path("unused-managed-tree"), "3.15.2", "embed",
                                     offline=True, seams={"fetch": unexpected, "resolver_run": unexpected})
    assert result.state == "unverifiable" and "offline" in result.reason


@pytest.mark.parametrize("offline", [False, True])
@pytest.mark.parametrize("force", [False, True])
def test_applied_minor_update_always_plans_target_restore_preflight(tmp_path, monkeypatch, offline, force):
    sys_dir = tmp_path / "_sys"
    monkeypatch.setattr(repair, "_python_pin", lambda *a:
                        {"version": "3.14.8", "url": "", "sha256": None})
    monkeypatch.setattr(repair, "python_update_status", lambda *a, **k: {
        "installed": "3.14.8", "discovery": {}, "lines": [],
        "patch": None, "readiness": None, "checked": False})

    readiness_calls = []
    def readiness(s, target, url, **kw):
        readiness_calls.append(kw["offline"])
        return repair.PythonReadiness(target, url, (), "ok", "")

    monkeypatch.setattr(repair, "_minor_readiness", readiness)

    def unexpected(*a, **k):
        raise AssertionError("planning must not run the staged preflight")

    def engine(ctx, builder, setup):
        args = SimpleNamespace(to_version="3.15.2", latest=False, offline=offline,
                               refresh=False, force=force, apply=True,
                               allow_major_runtime_upgrade=False)
        return builder(sys_dir, tmp_path, {}, cli_args=args, seams={"runner": unexpected})

    monkeypatch.setattr(repair, "_repair_engine_main", engine)
    plan = repair.update_env_main({}, {"python"})
    assert readiness_calls == [offline]
    names = [s.name for s in plan["steps"]]
    assert names.index("minor-restore-preflight") < names.index("stage")
    assert names.index("minor-restore-preflight") < names.index("quarantine-venv")
    assert names.index("minor-restore-preflight") < names.index("quarantine-python")
    assert plan["spec"][0]["params"]["offline"] == offline
    assert plan["spec"][0]["params"]["force"] == force


@pytest.mark.parametrize("force", [False, True])
@pytest.mark.parametrize("target_flags", [["--to", "3.15.2"], ["--latest"]])
def test_minor_jump_requires_preflight_unless_forced(tmp_path, monkeypatch, force, target_flags):
    _discovery(monkeypatch)
    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.14.8")
    monkeypatch.setattr(repair.subprocess, "run", lambda *a, **k:
                        SimpleNamespace(returncode=1, stdout="", stderr="ERROR: No matching distribution found for pywinpty"))
    args = target_flags + (["--force"] if force else [])
    result = _plan(tmp_path, args, {"python"})
    if force:
        params = result["plan"]["spec"][0]["params"]
        assert params["target_version"] == "3.15.2" and params["force"] is True
        assert "--force overrides" in "\n".join(result["plan"]["summary"])
    else:
        assert result["exit_code"] == 11
        assert "no compatible dependency set" in result["detail"] and "Use --force" in result["detail"]


@pytest.fixture
def latest_python(monkeypatch):
    _discovery(monkeypatch)
    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.14.8")
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {
        "manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "journal": None})
    monkeypatch.setattr(python_manager, "plan_python_update", lambda *a, **k: [
        env_ops.Step("update-python", lambda ctx: pytest.fail("preview must not execute"))])
    calls = []
    def fetch(url, *, method="GET"):
        calls.append((url, method))
        assert method == "HEAD"
        return None
    monkeypatch.setattr(repair, "_python_fetch", fetch)
    return calls


def test_latest_python_targets_highest_stable_and_preflights_without_applying(
        tmp_path, latest_python, monkeypatch):
    monkeypatch.setattr(env_ops, "execute", lambda *a, **k: pytest.fail("must preview"))
    resolver_calls = []
    monkeypatch.setattr(repair.subprocess, "run", lambda argv, **k:
                        resolver_calls.append(argv) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    result = _plan(tmp_path, ["--latest"], {"python"})
    assert result["exit_code"] == 0 and result["detail"] == "dry run"
    params = result["plan"]["spec"][0]["params"]
    assert params["target_version"] == "3.15.2" and not params["allow_major"]
    assert params["url"].endswith("/3.15.2/python-3.15.2-embed-amd64.zip")
    assert latest_python == [(params["url"], "HEAD")]
    assert len(resolver_calls) == 1


@pytest.mark.parametrize("preview", [False, True])
def test_latest_python_short_yes_requests_handoff_unless_previewing(
        tmp_path, latest_python, monkeypatch, preview):
    monkeypatch.setattr(repair, "_minor_readiness", lambda s, target, url, **k:
                        repair.PythonReadiness(target, url, (), "ok"))
    from core import updater
    handoffs = []
    monkeypatch.setattr(repair, "_in_runner", lambda: False)
    monkeypatch.setattr(repair, "_handoff_result", lambda s, label:
                        handoffs.append(label) or {"status": "success", "exit_code": 75})
    flags = ["--dry-run"] if preview else []
    args = updater._env_update_args(["-o", "python", "--latest", "-y", *flags])
    result = _plan(tmp_path, args, {"python"})
    assert result["exit_code"] == (0 if preview else 75)
    assert handoffs == ([] if preview else ["update"])


@pytest.mark.parametrize("flags", [[], ["--allow-major-runtime-upgrade"], ["--force"]])
def test_latest_python_never_downgrades(tmp_path, latest_python, monkeypatch, flags):
    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.16.1")
    result = _plan(tmp_path, ["--latest", *flags], {"python"}, pin_version="3.14.8")
    assert result["exit_code"] == 0
    assert latest_python == []
    assert all(item["params"]["target_version"] == "3.16.1"
               and not item["params"]["allow_downgrade"] for item in result["plan"]["spec"])


@pytest.mark.parametrize("allow", [False, True])
def test_latest_python_keeps_major_guard(tmp_path, latest_python, monkeypatch, allow):
    from core import version_resolver
    monkeypatch.setattr(version_resolver, "resolve_latest", lambda *a, **k: {
        "status": "ok", "latest_version": "4.0.1"})
    flags = ["--allow-major-runtime-upgrade"] if allow else []
    result = _plan(tmp_path, ["--latest", "--force", *flags], {"python"})
    if allow:
        assert result["exit_code"] == 0
        assert result["plan"]["spec"][0]["params"]["allow_major"]
        assert latest_python[0][1] == "HEAD"
    else:
        assert result["exit_code"] == 11 and "Blocked major" in result["detail"]
        assert latest_python == []


@pytest.mark.parametrize("failure", ["offline", "error", "exception", "missing", "prerelease"])
def test_latest_python_unavailable_never_falls_back_to_pin(
        tmp_path, latest_python, monkeypatch, failure):
    from core import version_resolver
    def resolve(*a, **k):
        if failure == "offline":
            pytest.fail("offline must not fetch")
        if failure == "exception":
            raise OSError("network unavailable")
        return {"status": "error" if failure == "error" else "ok",
                "latest_version": "3.15.0rc1" if failure == "prerelease" else None}
    monkeypatch.setattr(version_resolver, "resolve_latest", resolve)
    flags = ["--offline"] if failure == "offline" else []
    result = _plan(tmp_path, ["--latest", "--force", *flags], {"python"})
    assert result["exit_code"] == 11 and "latest unavailable" in result["detail"]
    assert "falling back" not in result["detail"] and latest_python == []


@pytest.mark.parametrize("installed", ["3.15.1", "3.15.2"])
def test_latest_python_patch_or_current_skips_minor_preflight(
        tmp_path, latest_python, monkeypatch, installed):
    monkeypatch.setattr(repair, "_installed_python", lambda *a: installed)
    result = _plan(tmp_path, ["--latest"], {"python"})
    assert result["exit_code"] == 0 and latest_python == []
    assert bool(result["plan"]["spec"]) == (installed == "3.15.1")


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


@pytest.mark.parametrize("state,reason", [
    ("ok", ""), ("blocked", "no compatible dependency set"),
    ("unverifiable", "network unavailable"),
])
def test_latest_execution_reuses_advice_readiness_before_mutation(
        tmp_path, latest_python, monkeypatch, state, reason):
    original = repair.python_update_status
    statuses, calls = [], []
    def status(*a, **k):
        result = original(*a, **k)
        statuses.append(result)
        return result
    def resolve(*a, **k):
        calls.append(True)
        return repair.PythonReadiness("3.15.2", a[2], (), state, reason)
    monkeypatch.setattr(repair, "python_update_status", status)
    monkeypatch.setattr(repair, "_minor_readiness", resolve)
    monkeypatch.setattr(repair, "_in_runner", lambda: True)
    executions = []
    monkeypatch.setattr(env_ops, "execute", lambda *a, **k:
                        executions.append(True) or {"status": "success"})
    result = _plan(tmp_path, ["--latest", "--apply", "--yes"], {"python"})
    assert len(calls) == 1
    assert statuses[0]["readiness"].state == state
    for key in ("lines", "report_lines"):
        advice = statuses[0][key]
        assert ("  Next: engram update -o python --latest -y" in advice) == (
            state == "ok")
        if state == "ok":
            index = advice.index("  Next: engram update -o python --latest -y")
            assert advice[index - 1] == (
                "Python 3.15 dependency readiness verified.")
    assert ("engram update -o python --latest -y" in statuses[0]["commands"]) == (state == "ok")
    assert result["exit_code"] == (0 if state == "ok" else 11)
    assert bool(executions) == (state == "ok")
    if state != "ok":
        assert reason in result["detail"]
        assert not (tmp_path / "_sys/env.ops.json").exists()


@pytest.mark.parametrize("mode", ["apply", "resume"])
def test_committed_state_write_failure_keeps_cli_and_json_contract(mode, capsys, monkeypatch):
    from core import dispatcher
    failure = {"status": "failed", "phase": "COMMITTED", "exit_code": 1,
               "detail": "state writes failed", "post_failed": ["write-manifest"],
               "op_id": "write-fault", "failed_step": "write-manifest",
               "recovery": "engram repair --resume", "quiet": True}
    result = repair._cli_result(failure, mode=mode)
    assert result["status"] == "failed" and result["exit_code"] == 1
    assert result["phase"] == "COMMITTED" and result["op_id"] == "write-fault"
    assert result["post_failed"] == ["write-manifest"]
    assert json.loads(json.dumps(result))["recovery"] == "engram repair --resume"
    assert result["quiet"] is True
    assert dispatcher._result_failed(result)
    monkeypatch.setattr(repair, "repair_main", lambda ctx: result)
    with pytest.raises(dispatcher.PipelineFailure) as raised:
        dispatcher._run_operation("repair", {"module": "core.repair", "method": "repair_main"}, {})
    assert raised.value.exit_code == 1 and raised.value.quiet is True
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("force", [False, True])
def test_applied_minor_update_force_does_not_override_restore_failure(tmp_path, monkeypatch, capsys, force):
    """F-03: Missing planning readiness can be waived; actual restore failures cannot."""
    import zipfile

    sys_dir = tmp_path / "_sys"
    (sys_dir / "env" / "python").mkdir(parents=True)
    (sys_dir / "env" / "venv" / "Scripts").mkdir(parents=True)
    (sys_dir / "data" / "state").mkdir(parents=True)

    archive, _ = python_manager.cache_paths(sys_dir, "3.15.2")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("python.exe", "fake target interpreter")

    def unexpected(*a, **kw):
        pytest.fail("preflight test must not download or run real pip")

    def runner(argv, timeout):
        assert argv[1:] == ["--version"]
        return 0, "Python 3.15.2"

    steps = python_manager.plan_python_update(
        sys_dir, "3.15.2", url="https://example.invalid/py.zip", force=force,
        installed="3.14.8", had_venv=True, runner=runner, downloader=unexpected,
    )
    preflight_step = next(s for s in steps if s.name == "minor-restore-preflight")
    monkeypatch.setattr(python_manager.venv_manager, "build_snapshot", lambda *a, **kw: {})
    calls = []

    def failing_restore(*a, **kw):
        calls.append(a)
        raise RuntimeError("required artifacts unavailable offline")

    monkeypatch.setattr(python_manager, "preflight_restore", failing_restore)
    ctx = SimpleNamespace(op_id="test-force-op", data={}, paths={})
    with pytest.raises(RuntimeError, match="preflight failed"):
        preflight_step.do(ctx)
    assert len(calls) == 1
    assert "preflight_snapshot" not in ctx.data
    out = capsys.readouterr().out
    assert "--force overrides" not in out
    assert "Managed Python and venv unchanged" in out


def test_forced_minor_update_still_requires_dependency_integrity(tmp_path):
    sys_dir = tmp_path / "_sys"
    executable = sys_dir / "env" / "venv" / "Scripts" / "python.exe"
    executable.parent.mkdir(parents=True)
    executable.write_text("fake")
    calls = []

    def runner(argv, timeout):
        calls.append(argv)
        if argv[1:] == ["--version"]:
            return 0, "Python 3.15.2"
        assert argv == [str(executable), "-m", "pip", "check"]
        return 1, "dependency conflict"

    steps = python_manager.plan_python_update(
        sys_dir, "3.15.2", url="https://example.invalid/py.zip", force=True,
        installed="3.14.8", had_venv=True, runner=runner,
    )
    with pytest.raises(RuntimeError, match="dependency"):
        next(s for s in steps if s.name == "verify").do(SimpleNamespace(data={}))
    assert calls[-1] == [str(executable), "-m", "pip", "check"]



def test_update_env_main_accepts_check_flag_and_exits_1_when_unchecked(tmp_path, monkeypatch):
    """F-06: update_env_main parser accepts --check and exits 1 when discovery is unchecked."""
    sys_dir = tmp_path / "_sys"
    (sys_dir / "env" / "python").mkdir(parents=True)
    (sys_dir / "env" / "python" / "python.exe").write_text("fake")
    (sys_dir / "data" / "state").mkdir(parents=True)

    monkeypatch.setattr(repair, "_installed_python", lambda *a: "3.14.8")
    monkeypatch.setattr(repair, "_python_pin", lambda *a: {"version": "3.14.8", "url": "", "sha256": None})
    monkeypatch.setattr(repair.layout_migration, "supported_layout", lambda *a, **k: True)
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {
        "manifest": "ok", "drift": {"status": "consistent"}, "findings": [], "journal": None,
        "stale_registry": []
    })

    # Unchecked discovery (e.g. offline)
    ctx = {"sys_dir": sys_dir, "base_dir": tmp_path, "command": "update", "args": ["--check", "--offline"]}
    res = repair.update_env_main(ctx, {"python"})
    assert res.get("exit_code") == 1
    assert res.get("status") == "failed"


# First-download trust policy: strict mode is opt-in, rejects unpinned
# targets *before* a Python swap; default operation remains compatible.

@pytest.mark.parametrize(
    "sha",
    [None, "", "not-a-sha", "a" * 63, "z" * 64],
)
def test_strict_python_policy_refuses_unpinned_or_invalid_digest(
    tmp_path, monkeypatch, sha
):
    monkeypatch.setattr(repair, "_installed_python", lambda s, seams: "3.14.8")
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {
        "manifest": "ok", "drift": {"status": "consistent"},
        "findings": [], "stale_registry": [], "journal": None, "lock": None,
    })
    out = _plan(
        tmp_path, ["--to", "3.14.9", "--require-pinned-sha256"],
        {"python"}, pin_version="3.14.9", sha=sha,
    )
    assert out["status"] == "failed"
    assert out["exit_code"] == 11
    assert "--require-pinned-sha256" in out["detail"]
    assert "trusted source" in out["detail"]


def test_strict_python_policy_accepts_pin_for_selected_target(tmp_path, monkeypatch):
    monkeypatch.setattr(repair, "_installed_python", lambda s, seams: "3.14.8")
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {
        "manifest": "ok", "drift": {"status": "consistent"},
        "findings": [], "stale_registry": [], "journal": None, "lock": None,
    })
    out = _plan(
        tmp_path, ["--to", "3.14.9", "--require-pinned-sha256"],
        {"python"}, pin_version="3.14.9", sha="ab" * 32,
    )
    assert out["status"] == "success"
    assert out["plan"]["spec"][0]["params"]["sha256"] == "ab" * 32
    assert any("PINNED_SHA256" in line for line in out["plan"]["summary"])


def test_strict_python_policy_rejects_different_target_even_with_pin(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(repair, "_installed_python", lambda s, seams: "3.14.8")
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {
        "manifest": "ok", "drift": {"status": "consistent"},
        "findings": [], "stale_registry": [], "journal": None, "lock": None,
    })
    out = _plan(
        tmp_path, ["--to", "3.14.9", "--require-pinned-sha256"],
        {"python"}, pin_version="3.14.8", sha="ab" * 32,
    )
    assert out["status"] == "failed"
    assert "--require-pinned-sha256" in out["detail"]


def test_strict_python_policy_requires_python_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(repair, "detect", lambda *a, **k: {
        "manifest": "ok", "drift": {"status": "consistent"},
        "findings": [], "stale_registry": [], "journal": None, "lock": None,
    })
    out = _plan(tmp_path, ["--require-pinned-sha256"], {"packages"})
    assert out["status"] == "failed"
    assert "--only python" in out["detail"]
