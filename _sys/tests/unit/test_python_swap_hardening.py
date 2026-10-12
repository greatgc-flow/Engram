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
from core import backups, env_manifest, env_ops, python_manager, repair  # noqa: E402

TARGET_PATCH = "3.14.9"
TARGET_MINOR = "3.15.0"


def tree_hash(root: Path, skip=(), marker: str | None = None) -> dict:
    """sha256 per file; `marker` (an install root) is replaced by <ROOT> so two installs compare equal."""
    out = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            if any(rel.startswith(s) for s in skip):
                continue
            data = p.read_bytes()
            if marker:
                for variant in (marker, marker.replace("\\", "/")):
                    data = data.replace(variant.encode(), b"<ROOT>")
            out[rel] = hashlib.sha256(data).hexdigest()
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
            if "--dry-run" in a:
                return 0, "Would install restored packages"
            sp = exe.parent.parent / "Lib" / "site-packages"
            for name in a[a.index("install") + 1:]:
                if name.startswith("-"):
                    continue
                base = Path(name).name if Path(name).is_dir() else name.split("==")[0].split(">=")[0]
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
        """Everything a rollback must restore bit-for-bit (the quarantine registry is excluded on purpose);
        absolute paths of THIS install are normalised so different installs can be compared."""
        marker = str(self.root)
        norm = lambda b: b.replace(marker.encode(), b"<ROOT>").replace(marker.replace("\\", "/").encode(), b"<ROOT>")
        manifest = json.dumps(env_manifest.read_manifest(self.sys).data, sort_keys=True).replace(
            marker.replace("\\", "\\\\"), "<ROOT>")
        return {**tree_hash(self.sys / "env", marker=marker),
                "runtimes.json": hashlib.sha256(norm((self.sys / "runtimes.json").read_bytes())).hexdigest(),
                "manifest": manifest}


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

def add_editable(world):
    source = world.root / "editable-project"
    source.mkdir()
    (source / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["missing-build-backend"]\n'
        'build-backend = "missing_backend"\n', encoding="utf-8")
    metadata = world.venv / "Lib" / "site-packages" / "editable-1.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Name: editable\nVersion: 1.0\nRequires-Dist: runtime-dep\n")
    (metadata / "direct_url.json").write_text(json.dumps(
        {"url": source.as_uri(), "dir_info": {"editable": True}}))
    return source


@pytest.mark.parametrize("output,offline,reason", [
    ("BackendUnavailable: Cannot import missing_backend", False, "editable build backend unavailable"),
    ("get_requires_for_build_editable: installing build dependencies failed", False, "editable build backend unavailable"),
    ("ResolutionImpossible: conflicting dependencies runtime-dep", False, "no compatible dependency set"),
    ("No matching distribution found for runtime-dep", True, "required artifacts unavailable offline"),
])
def test_minor_restore_preflight_faults_do_not_mutate_managed_state(minor_world, capsys, output, offline, reason):
    w = minor_world
    source = add_editable(w)
    before = w.snapshot()
    fake = w.runner

    def resolver_fault(argv, timeout):
        if "--dry-run" in argv:
            w.calls.append(argv)
            assert "-e" in argv and str(source) in argv and "pkg1==1.0" in argv
            assert "--ignore-installed" in argv
            assert "--no-build-isolation" not in argv and "--no-deps" not in argv
            assert ("--no-index" in argv) == offline
            assert str(w.venv) not in argv[0]
            return 1, output
        return fake(argv, timeout)

    w.runner = resolver_fault
    res = repair._cli_result(run(w, w.plan(offline=offline)), mode="apply", sys_dir=w.sys)
    assert res["exit_code"] == 11 and res["phase"] == "ROLLED_BACK"
    message = f"[Warning] Python minor update preflight failed: {reason}. Managed Python and venv unchanged."
    assert capsys.readouterr().out.count(message) == 1
    assert res["detail"] == message
    assert w.snapshot() == before
    assert not (w.sys / "env" / "python.new").exists()
    assert not backups.scan(w.sys).valid
    assert env_ops.active_journal(w.sys) is None


def test_offline_virtualenv_artifact_failure_precedes_swap(minor_world, capsys):
    w = minor_world
    before = w.snapshot()
    fake = w.runner

    def missing_artifact(argv, timeout):
        if "install" in argv and "virtualenv" in argv:
            assert "--no-index" in argv
            return 1, "virtualenv wheel unavailable"
        return fake(argv, timeout)

    w.runner = missing_artifact
    res = repair._cli_result(run(w, w.plan(offline=True)), mode="apply", sys_dir=w.sys)
    assert res["exit_code"] == 11
    assert w.snapshot() == before and not backups.scan(w.sys).valid
    assert "required artifacts unavailable offline" in capsys.readouterr().out


def test_offline_missing_python_archive_is_early_failure(minor_world, capsys):
    w = minor_world
    python_manager.cache_paths(w.sys, w.target)[0].unlink()
    before = w.snapshot()
    res = repair._cli_result(run(w, w.plan(offline=True)), mode="apply", sys_dir=w.sys)
    assert res["exit_code"] == 11
    assert w.snapshot() == before and not backups.scan(w.sys).valid
    assert not w.calls
    assert capsys.readouterr().out.count("[Warning] Python minor update preflight failed:") == 1


def test_cached_offline_minor_restore_checks_full_set_and_restores_editable(minor_world):
    w = minor_world
    source = add_editable(w)
    assert run(w, w.plan(offline=True))["phase"] == "COMMITTED"
    resolution = [c for c in w.calls if "--dry-run" in c]
    assert len(resolution) == 1 and str(source) in resolution[0]
    installs = [c for c in w.calls if "install" in c]
    assert all("--no-index" in c for c in installs)
    editable = [c for c in installs if "-e" in c and "--dry-run" not in c]
    assert editable and all("--no-deps" not in c and "--no-build-isolation" not in c for c in editable)


@pytest.mark.parametrize("fault", ["conflict", "timeout", "tool"])
@pytest.mark.parametrize("undo_fails", [False, True])
def test_minor_pip_check_blocks_commit_and_uses_existing_rollback(minor_world, capsys, fault, undo_fails):
    import subprocess
    w = minor_world
    before = w.snapshot()
    fake = w.runner

    def check_fault(argv, timeout):
        if argv[1:] == ["-m", "pip", "check"]:
            if fault == "timeout":
                raise subprocess.TimeoutExpired(argv, timeout)
            if fault == "tool":
                raise OSError("pip unavailable")
            return 1, "runtime-dep 2.0 conflicts with editable"
        return fake(argv, timeout)

    w.runner = check_fault
    steps = w.plan()
    if undo_fails:
        def fail_undo(ctx):
            raise OSError("injected undo failure")
        next(s for s in steps if s.name == "quarantine-python").undo = fail_undo
    res = repair._cli_result(run(w, steps), mode="apply", sys_dir=w.sys)
    assert res["exit_code"] == (13 if undo_fails else 12)
    assert res["phase"] == ("ROLLBACK_FAILED" if undo_fails else "ROLLED_BACK")
    assert capsys.readouterr().out.count("[Warning] Venv dependency verification failed:") == 1
    assert env_manifest.read_manifest(w.sys).data["python"]["version"] == w.installed
    if not undo_fails:
        assert w.snapshot() == before
        assert any(r.kind == "venv" and "failed-rebuild" in r.path.name for r in backups.scan(w.sys).valid)


def test_offline_patch_preserves_editable_and_keeps_dependency_warning_nonblocking(patch_world):
    w = patch_world
    add_editable(w)
    before = tree_hash(w.venv / "Lib" / "site-packages")
    fake = w.runner

    def patch_conflict(argv, timeout):
        if argv[1:] == ["-m", "pip", "check"]:
            w.calls.append(argv)
            return 1, "pre-existing dependency conflict"
        assert "--dry-run" not in argv and "-e" not in argv
        return fake(argv, timeout)

    w.runner = patch_conflict
    assert run(w, w.plan(offline=True))["phase"] == "COMMITTED"
    assert tree_hash(w.venv / "Lib" / "site-packages") == before
    assert not any("install" in c and Path(c[0]) == w.venv / "Scripts" / "python.exe" for c in w.calls)
    assert any(c[1:] == ["-m", "pip", "check"] for c in w.calls)

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


def add_pip_leftovers(world):
    site = world.venv / "Lib" / "site-packages"
    (site / "pkg1.py").write_text("original payload")
    (site / "pkg1-1.0.dist-info" / "RECORD").write_text("pkg1.py,,\n")
    for name in ("~stale.dist-info", "~older.egg-info"):
        info = site / name
        info.mkdir()
        (info / "METADATA").write_text("Name: pkg1\nVersion: 0.9\n")
        (info / "REQUESTED").touch()
    (site / "~").mkdir()
    return site


@pytest.mark.parametrize("target", [TARGET_PATCH, TARGET_MINOR])
def test_swap_quarantines_only_proven_duplicates_before_snapshot(tmp_path, monkeypatch, capsys, target):
    w = World(tmp_path, target=target)
    site = add_pip_leftovers(w)
    monkeypatch.setattr(python_manager, "default_holders", lambda paths: [])
    steps = w.plan(offline=True)
    names = [step.name for step in steps]
    assert names.index("quarantine-pip-leftovers") < names.index("snapshot-packages")
    if target == TARGET_MINOR:
        assert names.index("minor-restore-preflight") < names.index("plan-pip-leftovers")
    result = run(w, steps)
    assert result["status"] == "success"
    refs = [r for r in backups.scan(w.sys).valid if r.meta["reason"] == "quarantine pip leftover"]
    assert len(refs) == 2
    assert {Path(r.meta["source_path"]).name for r in refs} == {"~stale.dist-info", "~older.egg-info"}
    assert all((r.path / backups.PAYLOAD / "METADATA").read_text() ==
               "Name: pkg1\nVersion: 0.9\n" for r in refs)
    freeze = next(r for r in backups.scan(w.sys).valid if r.kind == "venv-freeze")
    packages = json.loads((freeze.path / backups.PAYLOAD / "snapshot.json").read_text())["packages"]
    assert [(p["name"], p["version"]) for p in packages] == [("pkg1", "1.0")]
    text = capsys.readouterr().out
    assert text.count("[Warning] Pip leftover quarantined:") == 2
    assert f"[Warning] Pip leftover kept: {site / '~'}." in text
    if target == TARGET_PATCH:
        assert (site / "~").exists() and (site / "pkg1.py").read_text() == "original payload"
        assert not any("--dry-run" in call or "-e" in call for call in w.calls)
    else:
        old = next(r for r in backups.scan(w.sys).valid if r.meta["source_path"] == str(w.venv))
        assert (old.path / backups.PAYLOAD / "Lib" / "site-packages" / "~").exists()


@pytest.mark.parametrize("target", [TARGET_PATCH, TARGET_MINOR])
@pytest.mark.parametrize("action", ["move-failure", "rollback", "resume", "mid-move-resume", "mid-move-rollback"])
def test_swap_leftover_faults_preserve_identity(tmp_path, monkeypatch, target, action):
    w = World(tmp_path, target=target)
    site = add_pip_leftovers(w)
    before = w.snapshot()
    monkeypatch.setattr(python_manager, "default_holders", lambda paths: [])
    move = backups._move_dir
    hit = []

    def fault(src, dst, **kwargs):
        if Path(src).parent == site and Path(src).name.startswith("~"):
            hit.append(str(src))
            if len(hit) == 2 and action == "move-failure":
                raise OSError("mock move failure")
            if len(hit) == 2 and action.startswith("mid-move"):
                raise env_ops.SimulatedCrash("crash between leftover moves")
        return move(src, dst, **kwargs)

    monkeypatch.setattr(backups, "_move_dir", fault)
    if action == "move-failure":
        result = run(w, w.plan())
        assert result["exit_code"] == 12 and result["phase"] == "ROLLED_BACK"
        assert w.snapshot() == before
        assert not any(call[1:3] == ["-m", "virtualenv"] and call[-1] == str(w.venv)
                       for call in w.calls)
        return
    with pytest.raises(env_ops.SimulatedCrash):
        run(w, w.plan(), crash_after=None if action.startswith("mid-move") else "swap")
    monkeypatch.setattr(backups, "_move_dir", move)
    active = env_ops.active_journal(w.sys)
    assert set(active["data"]["pip_swap_candidates"]) == {
        str(site / "~stale.dist-info"), str(site / "~older.egg-info")}
    if action.endswith("rollback"):
        result = env_ops.rollback(w.sys, lambda active: w.plan())
        assert result["exit_code"] == 12 and w.snapshot() == before
    else:
        result = env_ops.resume(w.sys, lambda active: w.plan())
        assert result["status"] == "success"
        assert not (site / "~stale.dist-info").exists()
        refs = [r for r in backups.scan(w.sys).valid if r.meta["reason"] == "quarantine pip leftover"]
        assert len(refs) == 2 and all(r.meta["op_id"] == "op-1" for r in refs)
        assert all((r.path / backups.PAYLOAD / "METADATA").read_text() ==
                   "Name: pkg1\nVersion: 0.9\n" for r in refs)


@pytest.mark.parametrize("failed", [("write-pin",), ("write-manifest",),
                                   ("write-pin", "write-manifest")])
def test_swap_post_write_failure_stays_committed_and_retries_only_pending(patch_world, capsys, failed):
    w = patch_world
    steps = w.plan()
    for step in steps:
        if step.name in failed:
            step.do = lambda ctx: (_ for _ in ()).throw(PermissionError("mock disk full"))
    result = repair._cli_result(run(w, steps), mode="apply", sys_dir=w.sys)
    assert result["status"] == "failed" and result["exit_code"] == 1
    assert result["phase"] == "COMMITTED" and result["post_failed"] == list(failed)
    assert "engram repair --resume (operation op-1)" in result["recovery"]
    assert "[Warning] Python update committed, but state writes failed:" in capsys.readouterr().out
    assert (w.sys / "env" / "python" / "python.exe").read_text() == TARGET_PATCH
    assert (w.venv / "Scripts" / "python.exe").read_text() == TARGET_PATCH
    refs = backups.scan(w.sys).valid
    assert refs and all((r.path / backups.PAYLOAD).exists() for r in refs)
    calls = list(w.calls)
    recovered = repair._cli_result(env_ops.resume(w.sys, lambda active: w.plan()), mode="resume", sys_dir=w.sys)
    assert recovered["status"] == "success" and recovered["exit_code"] == 0
    assert calls == w.calls
    assert json.loads((w.sys / "runtimes.json").read_text())["runtimes"]["python"]["version"] == TARGET_PATCH
    assert env_manifest.read_manifest(w.sys).data["python"]["version"] == TARGET_PATCH
    assert env_ops.active_journal(w.sys) is None
