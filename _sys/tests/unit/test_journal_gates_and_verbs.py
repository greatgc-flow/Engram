"""Entry-point gates for an interrupted environment operation (design section 9, T-F2) and the new
`engram repair` / `engram relocate` verbs, `engram update --only python|venv|packages` routing.

A non-terminal journal must block mutating verbs in engram.cmd, must stop bootstrap.bat from extracting a
fresh Python over a half-swapped tree, and must let `repair` run on the first working interpreter
(env\\python -> env\\python.new -> runner copy) when env\\python is missing.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pycopy import copy_python

from _sys.core.root import find_root

REPO_ROOT = find_root(__file__).parent
ENGRAM_CMD = REPO_ROOT / "engram.cmd"
BOOTSTRAP = REPO_ROOT / "_sys" / "core" / "bootstrap.bat"
DISPATCH = REPO_ROOT / "_sys" / "core" / "dispatch.bat"


def _record(seq, event, **kw):
    rec = {"seq": seq, "ts": "2026-10-02T00:00:00Z", "event": event, **kw, "crc": "00000000"}
    return json.dumps(rec, separators=(",", ":"))


def write_journal(root: Path, phases):
    state = root / "_sys" / "data" / "state"
    state.mkdir(parents=True, exist_ok=True)
    lines = [_record(i + 1, "PHASE", name=name) for i, name in enumerate(phases)]
    (state / "env-op.journal.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def root(tmp_path: Path):
    r = tmp_path / "a&b!"          # '&' and '!' in the path on purpose (CONVENTION 2.6)
    r.mkdir()
    (r / "engram.cmd").write_text(ENGRAM_CMD.read_text(encoding="utf-8"), encoding="utf-8")
    core = r / "_sys" / "core"
    core.mkdir(parents=True)
    (core / "version.json").write_text('{"version": "3.5.0"}', encoding="utf-8")
    (core / "dispatch.bat").write_text(
        "@echo off\r\necho DISPATCH_PIPELINE=%1\r\necho DISPATCH_ARGS=%*\r\nexit /b 0\r\n", encoding="utf-8")
    py = r / "_sys" / "env" / "python"
    py.mkdir(parents=True)
    copy_python(py / "python.exe")
    state = r / "_sys" / "data" / "state"
    state.mkdir(parents=True)
    (state / "layout.json").write_text('{"layout_version": 2}', encoding="utf-8")
    return r


def _cmd_line(script: Path, args) -> str:
    quoted = " ".join(f'"{a}"' if (" " in a or "!" in a or "\\" in a) else a for a in args)
    return f'cmd.exe /c ""{script}" {quoted}"' if quoted else f'cmd.exe /c ""{script}""'


def _run(script: Path, args, cwd: Path, extra_env=None):
    return subprocess.run(_cmd_line(script, args), cwd=str(cwd), capture_output=True, text=True, encoding="mbcs",
                          errors="replace", env={**os.environ, **(extra_env or {})}, timeout=120)


def run_engram(root, *args):
    return _run(root / "engram.cmd", args, root, {"ENGRAM_CALLER_CWD": str(root)})


# ---- gate in engram.cmd --------------------------------------------------------------------------------

@pytest.mark.parametrize("phase", ["PLANNED", "STEPS_RUNNING", "ROLLING_BACK", "ROLLBACK_FAILED"])
def test_non_terminal_journal_blocks_mutating_verbs(root, phase):
    write_journal(root, ["PLANNED", "STEPS_RUNNING"] if phase == "STEPS_RUNNING" else ["PLANNED", phase]
                  if phase != "PLANNED" else ["PLANNED"])
    for verb in ("tidy", "update", "uninstall"):
        proc = run_engram(root, verb)
        assert proc.returncode == 14, (verb, proc.stdout, proc.stderr)
        assert "interrupted" in proc.stdout.lower()
        assert "engram repair --resume" in proc.stdout and "engram repair --rollback" in proc.stdout
        assert "DISPATCH_PIPELINE" not in proc.stdout


def test_journal_gate_injection_hardening(root):
    write_journal(root, ["PLANNED", "STEPS_RUNNING & echo PWNED_MARKER"])
    proc = run_engram(root, "tidy")
    assert proc.returncode == 14, (proc.stdout, proc.stderr)
    assert "PWNED_MARKER" not in proc.stdout.splitlines()


@pytest.mark.parametrize("phases", [["PLANNED", "STEPS_RUNNING", "COMMITTED"], ["PLANNED", "STEPS_RUNNING", "ROLLING_BACK", "ROLLED_BACK"]])
def test_terminal_journal_does_not_block(root, phases):
    write_journal(root, phases)
    proc = run_engram(root, "tidy")
    assert proc.returncode == 0 and "DISPATCH_PIPELINE=tidy" in proc.stdout


def test_no_journal_does_not_block(root):
    proc = run_engram(root, "tidy")
    assert proc.returncode == 0 and "DISPATCH_PIPELINE=tidy" in proc.stdout


@pytest.mark.parametrize("verb,pipeline", [("doctor", "doctor"), ("repair", "repair"), ("relocate", "relocate"),
                                            ("snapshots", "snapshots")])
def test_recovery_and_read_only_verbs_pass_the_gate(root, verb, pipeline):
    write_journal(root, ["PLANNED", "STEPS_RUNNING"])
    proc = run_engram(root, verb)
    assert proc.returncode == 0, proc.stdout
    assert f"DISPATCH_PIPELINE={pipeline}" in proc.stdout


def test_help_and_version_pass_the_gate(root):
    write_journal(root, ["PLANNED", "STEPS_RUNNING"])
    assert run_engram(root, "help").returncode == 0
    assert run_engram(root, "version").returncode == 0


def test_plain_engram_with_missing_python_and_active_journal_does_not_bootstrap(root):
    write_journal(root, ["PLANNED", "STEPS_RUNNING"])
    (root / "_sys" / "env" / "python" / "python.exe").unlink()
    proc = run_engram(root)                      # plain `engram` = first-run bootstrap path
    assert proc.returncode == 14
    assert "interrupted" in proc.stdout.lower()


# ---- new verbs ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("args,pipeline", [(["repair"], "repair"), (["repair", "--apply", "--yes"], "repair"),
                                            (["relocate", "--from", "D:\\old"], "relocate")])
def test_new_verbs_dispatch(root, args, pipeline):
    proc = run_engram(root, *args)
    assert proc.returncode == 0 and f"DISPATCH_PIPELINE={pipeline}" in proc.stdout


@pytest.mark.parametrize("verb", ["repair", "relocate"])
@pytest.mark.parametrize("flag", ["--help", "-h", "help", "/?"])
def test_new_verbs_help_bypasses_the_not_set_up_check(root, verb, flag):
    (root / "_sys" / "env" / "python" / "python.exe").unlink()
    proc = run_engram(root, verb, flag)
    assert "Engram is not set up" not in proc.stdout


def test_new_verbs_are_listed_in_help(root):
    out = run_engram(root, "help").stdout
    assert "engram repair" in out and "engram relocate" in out


def test_repair_without_python_and_without_venv_says_not_set_up(root):
    (root / "_sys" / "env" / "python" / "python.exe").unlink()
    proc = run_engram(root, "repair")
    assert proc.returncode == 1 and "Engram is not set up" in proc.stdout


@pytest.mark.parametrize("verb", ["repair", "relocate", "snapshots", "doctor"])
def test_recovery_verbs_without_python_but_with_venv_point_at_bootstrap(root, verb):
    (root / "_sys" / "env" / "python" / "python.exe").unlink()
    (root / "_sys" / "env" / "venv").mkdir()
    proc = run_engram(root, verb)
    assert proc.returncode == 1
    assert "Managed Python is missing" in proc.stdout
    assert "_sys\\core\\bootstrap.bat" in proc.stdout and "engram repair" in proc.stdout
    assert "Engram is not set up" not in proc.stdout


def test_other_verbs_without_python_with_venv_still_say_not_set_up(root):
    (root / "_sys" / "env" / "python" / "python.exe").unlink()
    (root / "_sys" / "env" / "venv").mkdir()
    proc = run_engram(root, "tidy")
    assert proc.returncode == 1 and "Engram is not set up" in proc.stdout


def test_help_lists_each_recovery_verb_once(root):
    out = run_engram(root, "help").stdout
    for verb in ("repair", "relocate", "snapshots"):
        assert out.count(f"engram {verb} ") == 1, verb


# ---- dispatch.bat: alternate interpreter for an interrupted swap ---------------------------------------------

@pytest.fixture
def dispatch_root(tmp_path: Path):
    r = tmp_path / "a&b root"
    core = r / "_sys" / "core"
    core.mkdir(parents=True)
    shutil.copy(DISPATCH, core / "dispatch.bat")
    (core / "dispatcher.py").write_text(
        "import sys\nprint('RAN_WITH=' + sys.executable)\nprint('ARGS=' + ' '.join(sys.argv[1:]))\n", encoding="utf-8")
    (r / "_sys" / "data" / "state").mkdir(parents=True)
    return r


def run_dispatch(r, *args):
    return _run(r / "_sys" / "core" / "dispatch.bat", args, r)


def test_dispatch_falls_back_to_python_new_for_repair_when_a_journal_is_active(dispatch_root):
    r = dispatch_root
    write_journal(r, ["PLANNED", "STEPS_RUNNING"])
    alt = r / "_sys" / "env" / "python.new"
    alt.mkdir(parents=True)
    copy_python(alt / "python.exe")
    proc = run_dispatch(r, "repair", "--resume")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    recover_line = next((line for line in proc.stdout.splitlines() if line.startswith("[i] Recover")), "")
    assert "python.new" in recover_line and "ARGS=repair --resume" in proc.stdout
    assert str(alt / "python.exe") not in recover_line
    assert f"RAN_WITH={alt / 'python.exe'}" in proc.stdout.splitlines()


def test_dispatch_falls_back_to_the_runner_copy(dispatch_root):
    r = dispatch_root
    write_journal(r, ["PLANNED", "STEPS_RUNNING"])
    runner = r / "_sys" / "data" / "temp" / "env-op" / "op-1" / "runner"
    runner.mkdir(parents=True)
    copy_python(runner / "python.exe")
    proc = run_dispatch(r, "repair", "--rollback")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    recover_line = next((line for line in proc.stdout.splitlines() if line.startswith("[i] Recover")), "")
    assert "runner" in recover_line
    assert str(runner / "python.exe") not in recover_line
    assert f"RAN_WITH={runner / 'python.exe'}" in proc.stdout.splitlines()


def test_dispatch_falls_back_to_backup_payload_over_python_new(dispatch_root):
    r = dispatch_root
    write_journal(r, ["PLANNED", "STEPS_RUNNING"])
    backup = r / "_sys" / "data" / "backups" / "env" / "python" / "bkp-1" / "payload"
    backup.mkdir(parents=True)
    copy_python(backup / "python.exe")
    
    alt = r / "_sys" / "env" / "python.new"
    alt.mkdir(parents=True)
    copy_python(alt / "python.exe")
    
    proc = run_dispatch(r, "repair", "--rollback")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    recover_line = next((line for line in proc.stdout.splitlines() if line.startswith("[i] Recover")), "")
    assert "backup" in recover_line
    assert str(backup / "python.exe") not in recover_line
    assert f"RAN_WITH={backup / 'python.exe'}" in proc.stdout.splitlines()


def test_dispatch_runner_preferred_over_all(dispatch_root):
    r = dispatch_root
    write_journal(r, ["PLANNED", "STEPS_RUNNING"])
    
    runner = r / "_sys" / "data" / "temp" / "env-op" / "op-1" / "runner"
    runner.mkdir(parents=True)
    copy_python(runner / "python.exe")
    
    backup = r / "_sys" / "data" / "backups" / "env" / "python" / "bkp-1" / "payload"
    backup.mkdir(parents=True)
    copy_python(backup / "python.exe")
    
    alt = r / "_sys" / "env" / "python.new"
    alt.mkdir(parents=True)
    copy_python(alt / "python.exe")
    
    proc = run_dispatch(r, "repair", "--rollback")
    assert proc.returncode == 0 and "runner" in proc.stdout
    assert "backup" not in proc.stdout and "python.new" not in proc.stdout


def test_dispatch_does_not_use_an_alternate_interpreter_for_other_commands(dispatch_root):
    r = dispatch_root
    write_journal(r, ["PLANNED", "STEPS_RUNNING"])
    alt = r / "_sys" / "env" / "python.new"
    alt.mkdir(parents=True)
    copy_python(alt / "python.exe")
    proc = run_dispatch(r, "tidy")
    assert proc.returncode == 1 and "not initialized" in proc.stdout


def test_dispatch_without_a_journal_never_uses_python_new(dispatch_root):
    r = dispatch_root
    alt = r / "_sys" / "env" / "python.new"
    alt.mkdir(parents=True)
    copy_python(alt / "python.exe")
    proc = run_dispatch(r, "repair")
    assert proc.returncode == 1 and "not initialized" in proc.stdout


def test_handoff_file_roundtrips_mbcs(tmp_path):
    r = tmp_path / "한글 root"
    try:
        str(r).encode("mbcs")
    except UnicodeEncodeError:
        pytest.skip("cannot encode root path in mbcs")
        
    core = r / "_sys" / "core"
    core.mkdir(parents=True)
    try:
        probe = subprocess.run(
            ["cmd.exe", "/c", "echo", "ok"], cwd=str(r), capture_output=True,
            text=True, encoding="mbcs", errors="replace", timeout=120)
    except OSError as exc:
        pytest.skip(f"cmd.exe cannot run in the Korean directory: {exc}")
    if probe.returncode != 0 or probe.stdout.strip() != "ok":
        pytest.skip(
            f"cmd.exe cannot run 'echo ok' in the Korean directory "
            f"(exit {probe.returncode}): {probe.stderr}{probe.stdout}")
    shutil.copy(DISPATCH, core / "dispatch.bat")
    
    handoff_txt = r / "_sys" / "data" / "state" / "env-op" / "handoff.txt"
    runner_py = r / "_sys" / "data" / "temp" / "env-op" / "op-1" / "runner" / "python.exe"
    
    dispatcher_code = f"""import sys, os
if os.environ.get('ENGRAM_IN_RUNNER') == '1':
    print('SUCCESS_IN_RUNNER')
    sys.exit(0)
handoff = r'''{str(handoff_txt)}'''
runner = r'''{str(runner_py)}'''
os.makedirs(os.path.dirname(handoff), exist_ok=True)
os.makedirs(os.path.dirname(runner), exist_ok=True)
import shutil
from pathlib import Path
for _f in Path(sys.executable).parent.iterdir():
    if _f.is_file():
        shutil.copy(_f, Path(runner).parent / _f.name)
with open(handoff, 'wb') as f:
    sysdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    f.write((os.path.relpath(runner, sysdir) + "\\r\\n0\\r\\n").encode('ascii'))
sys.exit(75)
"""
    (core / "dispatcher.py").write_text(dispatcher_code, encoding="utf-8")
    
    py_dir = r / "_sys" / "env" / "python"
    py_dir.mkdir(parents=True)
    copy_python(py_dir / "python.exe")
    
    proc = _run(Path("_sys") / "core" / "dispatch.bat", ["tidy"], r)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "SUCCESS_IN_RUNNER" in proc.stdout


# ---- bootstrap.bat gate ------------------------------------------------------------------------------------------

def test_bootstrap_refuses_to_extract_python_while_a_journal_is_active(tmp_path):
    r = tmp_path / "root"
    core = r / "_sys" / "core"
    core.mkdir(parents=True)
    shutil.copy(BOOTSTRAP, core / "bootstrap.bat")
    (r / "_sys" / "runtimes.json").write_text(json.dumps({"runtimes": {"python": {
        "version": "3.14.8", "url": "https://invalid.example/python.zip", "get_pip_url": "https://invalid.example/get-pip.py"}}}),
        encoding="utf-8")
    write_journal(r, ["PLANNED", "STEPS_RUNNING"])
    proc = _run(core / "bootstrap.bat", ["--skip-update"], r, {"CI": "1"})
    assert proc.returncode == 14, proc.stdout + proc.stderr
    assert "interrupted" in proc.stdout.lower() and "engram repair --resume" in proc.stdout
    assert not (r / "_sys" / "env" / "python").exists()
    assert not (r / "_sys" / "data" / "setup-files").exists()      # nothing downloaded or created


def test_bootstrap_static_gate_precedes_every_download():
    text = BOOTSTRAP.read_text(encoding="utf-8")
    gate = text.index("env-op.journal.jsonl")
    assert gate < text.index("curl ")
    assert gate < text.index("Expand-Archive")
