"""End-to-end contract for the managed Python swap (design 6.2 / 9, review of 2026-10-02).

Runs the REAL plan (python_manager.plan_python_update + venv_repair steps) through the REAL env_ops engine on a
fake install tree. A fake runner emulates python.exe / virtualenv / pip by acting on the tmp tree, so a failure or a
crash injected at ANY step can be rolled back / resumed and the result compared bit-for-bit.

Findings covered (cc.deepthink review): resume/rollback rebuilt a DIFFERENT plan from the live disk (so rollback undid
nothing); rollback after a venv rebuild left a broken venv; verify ignored a missing/unhealthy venv; torn journal tails
wedged the install; failed journal rotation appended into the old journal.
"""
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

from _sys.core.root import find_root

sys.path.insert(0, str(find_root(__file__)))
from core import backups, env_manifest, env_ops, python_manager  # noqa: E402

TARGET_PATCH = "3.14.9"
TARGET_MINOR = "3.15.0"


def tree_hash(root: Path, skip=()) -> dict:
    out = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            if any(rel.startswith(s) for s in skip):
                continue
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


class World:
    """A fake install: interpreter 'python.exe' files hold their own version string."""

    def __init__(self, tmp_path, installed="3.14.8", target=TARGET_PATCH, with_venv=True):
        self.root = tmp_path
        self.sys = tmp_path / "_sys"
        self.installed, self.target = installed, target
        self.calls = []
        self.fail_virtualenv = False
        self.virtualenv_creates_nothing = False
        self.fail_pip = False
        self.missing_baseline = False
        env = self.sys / "env"
        py = env / "python"
        py.mkdir(parents=True)
        (py / "python.exe").write_text(installed)
        (py / "python314.dll").write_text("dll-" + installed)
        self.venv = env / "venv"
        if with_venv:
            (self.venv / "Scripts").mkdir(parents=True)
            (self.venv / "Scripts" / "python.exe").write_text(installed)
            (self.venv / "pyvenv.cfg").write_text(f"home = {py}\nversion = {installed}\n")
            di = self.venv / "Lib" / "site-packages" / "pkg1-1.0.dist-info"
            di.mkdir(parents=True)
            (di / "METADATA").write_text("Name: pkg1\nVersion: 1.0\n")
            (di / "REQUESTED").write_text("")
        (self.sys / "data" / "state").mkdir(parents=True)
        (self.sys / "runtimes.json").write_text(json.dumps(
            {"runtimes": {"python": {"version": installed, "url": "https://example.invalid/old.zip"}}}, indent=4))
        env_manifest.write_manifest(self.sys, {"schema_version": 1, "install_id": "i" * 36,
                                               "root": {"logical": str(tmp_path), "physical": str(tmp_path)},
                                               "python": {"version": installed}})
        # verified cache for the target (same naming as bootstrap.bat: <zip>.sha256)
        zip_path, sha_path = python_manager.cache_paths(self.sys, target)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("python.exe", target)
            zf.writestr("python314.dll", "dll-" + target)
            zf.writestr("python314._pth", "python314.zip\n.\n#import site\n")
        sha_path.write_text(hashlib.sha256(zip_path.read_bytes()).hexdigest())
        (self.sys / "data" / "setup-files" / "get-pip.py").write_text("# fake")

    # ---- fake runner ------------------------------------------------------------------------------
    def runner(self, argv, timeout):
        self.calls.append(list(argv))
        exe = Path(argv[0])
        a = argv[1:]
        if a == ["--version"]:
            return 0, f"Python {exe.read_text().strip()}"
        if a[:2] == ["-m", "virtualenv"]:
            if self.fail_virtualenv:
                return 1, "virtualenv failed"
            target = Path(a[-1])
            version = exe.read_text().strip()
            if self.virtualenv_creates_nothing:
                return 0, ""
            (target / "Scripts").mkdir(parents=True, exist_ok=True)
            (target / "Scripts" / "python.exe").write_text(version)
            (target / "pyvenv.cfg").write_text(f"home = {exe.parent}\nversion = {version}\n")
            (target / "Lib" / "site-packages").mkdir(parents=True, exist_ok=True)
            return 0, ""
        if a[:2] == ["-m", "pip"] and "check" in a:
            return 0, "No broken requirements found."
        if a[:2] == ["-m", "pip"] and "install" in a:
            if self.fail_pip:
                return 1, "pip failed"
            sp = exe.parent.parent / "Lib" / "site-packages"
            for name in a[a.index("install") + 1:]:
                if name.startswith("-"):
                    continue
                base = name.split("==")[0].split(">=")[0]
                di = sp / f"{base}-1.0.dist-info"
                di.mkdir(parents=True, exist_ok=True)
                (di / "METADATA").write_text(f"Name: {base}\nVersion: 1.0\n")
            return 0, ""
        if a and a[0] == "-c":
            script = a[1]
            if "print(json.dumps([list(sys.version_info" in script:
                v = [int(x) for x in exe.read_text().strip().split(".")]
                return 0, json.dumps([v, str(exe.parent.parent)])
            if "ProcessPoolExecutor" in script:
                return 0, ""
            if "find_spec" in script:
                return 0, json.dumps(["psutil"] if self.missing_baseline else [])
            if "ScriptMaker" in script:
                return 0, json.dumps({"regenerated": 0, "failed": []})
            return 0, ""
        return 0, ""

    def downloader(self, url, dest):
        raise AssertionError("the verified cache must be used; no download expected")

    def plan(self, **kw):
        kw.setdefault("installed", self.installed)
        return python_manager.plan_python_update(
            self.sys, self.target, url="https://example.invalid/p.zip", downloader=self.downloader, runner=self.runner,
            free_space=lambda p: 10 ** 12, holders=lambda ps: [], sleep=lambda s: None, **kw)

    def paths(self, op_id):
        return python_manager.allocate_paths(self.sys, op_id, env_ops.utc_now)

    def snapshot(self):
        """Everything a rollback must restore bit-for-bit (the quarantine registry is excluded on purpose)."""
        return {**tree_hash(self.sys / "env"), "runtimes.json": hashlib.sha256((self.sys / "runtimes.json").read_bytes()).hexdigest(),
                "manifest": json.dumps(env_manifest.read_manifest(self.sys).data, sort_keys=True)}


def run(world, steps, op_id="op-1", **kw):
    return env_ops.execute(world.sys, "update", steps, op_id=op_id, paths=world.paths(op_id), **kw)


def step_names(world, **kw):
    return [s.name for s in world.plan(**kw)]


@pytest.fixture
def patch_world(tmp_path):
    return World(tmp_path, "3.14.8", TARGET_PATCH)


@pytest.fixture
def minor_world(tmp_path):
    return World(tmp_path, "3.14.8", TARGET_MINOR)


# ---- happy paths --------------------------------------------------------------------------------------

def test_patch_update_replaces_python_refreshes_the_venv_and_commits(patch_world):
    w = patch_world
    res = run(w, w.plan())
    assert res["status"] == "success" and res["phase"] == "COMMITTED", res
    assert (w.sys / "env" / "python" / "python.exe").read_text() == TARGET_PATCH
    assert (w.venv / "Scripts" / "python.exe").read_text() == TARGET_PATCH            # interpreter refreshed in place
    assert (w.venv / "Lib" / "site-packages" / "pkg1-1.0.dist-info" / "METADATA").exists()   # packages untouched
    assert json.loads((w.sys / "runtimes.json").read_text())["runtimes"]["python"]["version"] == TARGET_PATCH
    assert env_manifest.read_manifest(w.sys).data["python"]["version"] == TARGET_PATCH
    py_backups = [r for r in backups.scan(w.sys).valid if r.kind == "python"]
    assert py_backups and all(r.meta["state"] == "committed" for r in py_backups)
    assert (py_backups[0].path / backups.PAYLOAD / "python.exe").read_text() == "3.14.8"


def test_minor_update_rebuilds_the_venv_and_restores_requested_packages(minor_world):
    w = minor_world
    res = run(w, w.plan())
    assert res["status"] == "success" and res["phase"] == "COMMITTED", res
    assert (w.venv / "Scripts" / "python.exe").read_text() == TARGET_MINOR
    assert (w.venv / "Lib" / "site-packages" / "pkg1-1.0.dist-info").exists()            # restored from the snapshot
    old = [r for r in backups.scan(w.sys).valid if r.kind == "venv"]
    assert old and (old[0].path / backups.PAYLOAD / "Scripts" / "python.exe").read_text() == "3.14.8"


# ---- determinism: resume/rollback must rebuild the SAME plan ------------------------------------------------

def test_the_plan_does_not_depend_on_what_the_disk_reports_when_installed_is_given(patch_world):
    w = patch_world
    names_before = step_names(w)
    (w.sys / "env" / "python" / "python.exe").write_text(TARGET_PATCH)     # the swap already happened
    assert step_names(w) == names_before                                    # classification came from `installed=`


def test_minor_plan_names_do_not_change_when_env_python_is_missing(minor_world):
    w = minor_world
    names = step_names(w)
    assert "quarantine-venv" in names or any("quarantine" in n and "venv" in n for n in names)
    import shutil
    shutil.rmtree(w.sys / "env" / "python")                                  # crash window: no interpreter at all
    assert step_names(w) == names


# ---- failure at every step => bit-for-bit rollback ------------------------------------------------------------

@pytest.mark.parametrize("which", ["patch", "minor"])
def test_failure_at_any_group_a_step_rolls_back_bit_for_bit(tmp_path, which):
    probe = World(tmp_path / "probe", "3.14.8", TARGET_PATCH if which == "patch" else TARGET_MINOR)
    names = [s.name for s in probe.plan() if s.group == "A"]
    assert len(names) >= 7
    for failing in names:
        w = World(tmp_path / f"w-{failing}", "3.14.8", TARGET_PATCH if which == "patch" else TARGET_MINOR)
        before = w.snapshot()
        steps = w.plan()
        for s in steps:
            if s.name == failing:
                real = s.do
                def boom(ctx, real=real):
                    raise RuntimeError(f"injected failure at {failing}")
                s.do = boom
        res = run(w, steps)
        assert res["status"] == "failed", (failing, res)
        assert res["phase"] == "ROLLED_BACK", (failing, res)
        assert w.snapshot() == before, f"rollback after failure at {failing} did not restore the tree"
        assert env_ops.active_journal(w.sys) is None


# ---- crash at every step => rollback (or resume) with a REBUILT plan -------------------------------------------

@pytest.mark.parametrize("which", ["patch", "minor"])
def test_crash_anywhere_then_rollback_with_a_rebuilt_plan_restores_everything(tmp_path, which):
    target = TARGET_PATCH if which == "patch" else TARGET_MINOR
    names = [s.name for s in World(tmp_path / "probe", "3.14.8", target).plan() if s.group == "A"]
    for crash in names:
        w = World(tmp_path / f"c-{crash}", "3.14.8", target)
        before = w.snapshot()
        with pytest.raises(env_ops.SimulatedCrash):
            run(w, w.plan(), crash_after=crash)
        assert env_ops.active_journal(w.sys) is not None
        # the rebuilt plan is built from the saved classification, NOT from the (now different) disk
        res = env_ops.rollback(w.sys, lambda active: w.plan())
        assert res["phase"] == "ROLLED_BACK", (crash, res)
        assert w.snapshot() == before, f"rollback after a crash at {crash} did not restore the tree"


@pytest.mark.parametrize("which", ["patch", "minor"])
def test_crash_anywhere_then_resume_converges_to_the_uninterrupted_result(tmp_path, which):
    target = TARGET_PATCH if which == "patch" else TARGET_MINOR
    ref = World(tmp_path / "ref", "3.14.8", target)
    assert run(ref, ref.plan())["phase"] == "COMMITTED"
    expected = ref.snapshot()
    names = [s.name for s in ref.plan(installed="3.14.8") if s.group == "A"]
    for crash in names:
        w = World(tmp_path / f"r-{crash}", "3.14.8", target)
        with pytest.raises(env_ops.SimulatedCrash):
            run(w, w.plan(), crash_after=crash)
        res = env_ops.resume(w.sys, lambda active: w.plan())
        assert res["status"] == "success" and res["phase"] == "COMMITTED", (crash, res)
        assert w.snapshot() == expected, f"resume after a crash at {crash} diverged from the uninterrupted run"


def test_rollback_refuses_when_a_started_step_is_missing_from_the_rebuilt_plan(patch_world):
    w = patch_world
    with pytest.raises(env_ops.SimulatedCrash):
        run(w, w.plan(), crash_after="swap")
    shorter = [s for s in w.plan() if s.name != "swap"]
    with pytest.raises(env_ops.JournalError, match="swap"):
        env_ops.rollback(w.sys, lambda active: shorter)
    with pytest.raises(env_ops.JournalError, match="swap"):
        env_ops.resume(w.sys, lambda active: shorter)


# ---- verify must really verify -------------------------------------------------------------------------------------

def test_verify_fails_when_a_rebuild_produced_no_venv(minor_world):
    w = minor_world
    w.virtualenv_creates_nothing = True
    before = w.snapshot()
    res = run(w, w.plan())
    assert res["status"] == "failed" and res["phase"] == "ROLLED_BACK", res
    assert w.snapshot() == before


def test_verify_fails_when_baseline_packages_are_missing_after_a_rebuild(minor_world):
    w = minor_world
    w.missing_baseline = True
    before = w.snapshot()
    res = run(w, w.plan())
    assert res["status"] == "failed" and res["phase"] == "ROLLED_BACK", res
    assert w.snapshot() == before


def test_a_failed_venv_creation_restores_python_and_the_old_venv(minor_world):
    w = minor_world
    w.fail_virtualenv = True
    before = w.snapshot()
    res = run(w, w.plan())
    assert res["status"] == "failed" and res["phase"] == "ROLLED_BACK", res
    assert w.snapshot() == before
    assert (w.sys / "env" / "python" / "python.exe").read_text() == "3.14.8"
    assert (w.venv / "Scripts" / "python.exe").read_text() == "3.14.8"


def test_pip_failure_during_restore_rolls_everything_back(minor_world):
    w = minor_world
    w.fail_pip = True
    before = w.snapshot()
    res = run(w, w.plan())
    assert res["status"] == "failed" and res["phase"] == "ROLLED_BACK", res
    assert w.snapshot() == before


def test_no_step_ever_deletes_the_venv_it_did_not_back_up(minor_world):
    """The old venv must exist in the registry before anything replaces it (no bare rmtree)."""
    w = minor_world
    seen = {}
    steps = w.plan()
    for s in steps:
        if s.name == "swap":
            real = s.do
            def spy(ctx, real=real):
                seen["venv_backup_exists_before_swap"] = any(
                    r.kind == "venv" for r in backups.scan(w.sys).valid)
                return real(ctx)
            s.do = spy
    run(w, steps)
    assert seen.get("venv_backup_exists_before_swap") is True


# ---- naming / allocation ------------------------------------------------------------------------------------------------

def test_cache_sha_file_uses_the_same_name_as_bootstrap_bat(tmp_path):
    zip_path, sha_path = python_manager.cache_paths(tmp_path, "3.14.9")
    assert zip_path.name == "python-3.14.9-embed-amd64.zip"
    assert sha_path.name == "python-3.14.9-embed-amd64.zip.sha256"      # bootstrap writes <zip>.sha256


def test_allocated_paths_cover_every_destination_the_plan_uses(tmp_path):
    p = python_manager.allocate_paths(tmp_path, "op-1", env_ops.utc_now)
    assert {"python_backup", "venv_backup", "freeze_backup", "venv_failed_backup", "venv_interp_backup"} <= set(p)
    assert "runner_dir" not in p                       # the runner lives outside the registry and is not journaled here
    root = backups.backups_root(tmp_path)
    for key in ("python_backup", "venv_backup", "venv_failed_backup", "venv_interp_backup", "freeze_backup"):
        assert Path(p[key]).parent.parent == root


def test_default_holders_report_processes_running_from_the_swap_targets(tmp_path):
    py = tmp_path / "env" / "python"
    py.mkdir(parents=True)
    out = json.dumps([{"ProcessId": 4242, "ExecutablePath": str(py / "python.exe")}])
    held = python_manager.default_holders([py], runner=lambda argv, t: (0, out))
    assert held and held[0]["pid"] == 4242
    assert python_manager.default_holders([py], runner=lambda argv, t: (1, "")) == []       # advisory only: never raises


# ---- env_ops: torn tail, failed rotation -----------------------------------------------------------------------------------

def _noop_steps(log):
    return [env_ops.Step(f"s{i}", (lambda ctx, i=i: log.append(i)), group="A") for i in range(1, 4)]


def test_resume_after_a_torn_journal_tail_appends_after_the_last_valid_record(tmp_path):
    sys_dir = tmp_path / "_sys"
    log = []
    with pytest.raises(env_ops.SimulatedCrash):
        env_ops.execute(sys_dir, "t", _noop_steps(log), crash_after="s1", op_id="op-t")
    jpath = env_ops.journal_path(sys_dir)
    with open(jpath, "ab") as fh:
        fh.write(b'{"seq":99,"ts":"x","event":"STEP","name":"s2","sta')      # torn mid-record, no newline
    res = env_ops.resume(sys_dir, lambda a: _noop_steps(log))
    assert res["status"] == "success" and res["phase"] == "COMMITTED", res
    records = env_ops.read_journal(sys_dir)
    assert records[-1].get("name") == "COMMITTED"                            # nothing is hidden behind the tear
    assert env_ops.active_journal(sys_dir) is None
    assert b'"sta\n' not in jpath.read_bytes() and jpath.read_bytes().endswith(b"\n")


def test_a_failed_journal_rotation_refuses_to_start_instead_of_appending_to_the_old_journal(tmp_path, monkeypatch):
    sys_dir = tmp_path / "_sys"
    log = []
    assert env_ops.execute(sys_dir, "t", _noop_steps(log), op_id="op-1")["phase"] == "COMMITTED"
    old = env_ops.journal_path(sys_dir).read_bytes()
    real_replace = os.replace

    def failing(src, dst, *a, **k):
        if str(dst).endswith(".done"):
            raise PermissionError("locked")
        return real_replace(src, dst, *a, **k)

    monkeypatch.setattr(os, "replace", failing)
    monkeypatch.setattr(env_ops.os, "replace", failing)
    with pytest.raises(env_ops.JournalError):
        env_ops.execute(sys_dir, "t", _noop_steps(log), op_id="op-2")
    assert env_ops.journal_path(sys_dir).read_bytes() == old                # old journal untouched
