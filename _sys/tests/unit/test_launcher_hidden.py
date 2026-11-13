"""Launcher process and log ownership, with every child process stubbed."""
import builtins
import os
import subprocess
import sys
from pathlib import Path

import pytest

import _sys.core.launcher as launcher


@pytest.fixture
def launch_setup(tmp_path, monkeypatch):
    base = tmp_path / "Engram with spaces"
    sys_dir = base / "_sys"
    vscode = sys_dir / "VS Code" / "Code.exe"
    vscode.parent.mkdir(parents=True)
    vscode.touch()
    (sys_dir / "env.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENGRAM_HIDDEN_LAUNCH", raising=False)
    monkeypatch.delenv("ENGRAM_CALLER_CWD", raising=False)
    monkeypatch.setattr(launcher.provisioner, "vscode_exe", lambda _: vscode)
    # This Windows-only creation flag is absent on other unit-test platforms.
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    launches = []

    def popen(argv, **kwargs):
        output = kwargs["stdout"]
        if output != subprocess.DEVNULL:
            assert not output.closed
            assert output.mode == "ab"
            output.write(b"VS Code output\n")
        assert kwargs["stderr"] == subprocess.STDOUT
        assert "ENGRAM_HIDDEN_LAUNCH" not in os.environ
        assert "ENGRAM_HIDDEN_LAUNCH" not in kwargs["env"]
        launches.append((argv, kwargs, Path.cwd()))
        return object()  # No wait API: the launcher must return immediately.

    def no_shell(*args, **kwargs):
        pytest.fail("unexpected subprocess.run (including cmd /k)")

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(subprocess, "run", no_shell)
    ctx = {"base_dir": base, "sys_dir": sys_dir, "args": []}
    return ctx, vscode, sys_dir / "data" / "logs" / "launcher", launches


def test_hidden_launch_is_silent_and_consumes_marker_before_build_env(
    launch_setup, monkeypatch, capsys,
):
    ctx, vscode, log_dir, launches = launch_setup
    monkeypatch.setenv("ENGRAM_HIDDEN_LAUNCH", "1")
    original_build_env = launcher.build_env

    def build_env(*args):
        assert "ENGRAM_HIDDEN_LAUNCH" not in os.environ
        return original_build_env(*args)

    def seed_warning(*args):
        print("settings warning")
        print("settings stderr", file=sys.stderr)

    monkeypatch.setattr(launcher, "build_env", build_env)
    monkeypatch.setattr(launcher.provisioner, "seed_vscode_default_settings", seed_warning)
    # Also exercise the root-drift diagnostic in hidden mode.
    (ctx["sys_dir"] / "data").mkdir()
    (ctx["sys_dir"] / "data" / "last_base_dir.txt").write_text(
        str(ctx["base_dir"].parent / "old install"), encoding="utf-8",
    )

    assert launcher.main(ctx) is None

    assert capsys.readouterr() == ("", "")
    assert len(launches) == 1
    argv, kwargs, cwd = launches[0]
    assert argv == [str(vscode), "."]
    assert cwd == ctx["base_dir"]
    assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert kwargs["stdout"].closed
    assert (log_dir / "vscode.log").read_bytes() == b"VS Code output\n"
    start_log, = log_dir.glob("start_*.log")
    content = start_log.read_text(encoding="utf-8")
    assert "root changed" in content
    assert "settings warning" in content and "settings stderr" in content
    assert "[OK] VS Code:" in content and "[Done]" in content
    assert content.index("root changed") < content.index("Started :")
    assert content.index("BASE    :") < content.index("settings warning")
    assert content.index("settings warning") < content.index("settings stderr")
    assert content.index("settings stderr") < content.index("[OK] VS Code:")
    assert content.index("[OK] VS Code:") < content.index("[Done]")


def test_two_double_clicks_launch_twice_and_append(launch_setup, monkeypatch, capsys):
    ctx, _, log_dir, launches = launch_setup
    for _ in range(2):
        monkeypatch.setenv("ENGRAM_HIDDEN_LAUNCH", "1")
        launcher.main(ctx)

    assert len(launches) == 2
    assert all(call[1]["stdout"].closed for call in launches)
    assert (log_dir / "vscode.log").read_bytes() == b"VS Code output\n" * 2
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("hidden", [False, True])
def test_explicit_workspace_with_spaces_redirects_output(launch_setup, monkeypatch, hidden):
    ctx, vscode, log_dir, launches = launch_setup
    target = ctx["base_dir"] / "workspace with spaces"
    target.mkdir()
    ctx["args"] = [str(target)]
    if hidden:
        monkeypatch.setenv("ENGRAM_HIDDEN_LAUNCH", "1")

    launcher.main(ctx)

    argv, kwargs, cwd = launches[0]
    assert argv == [str(vscode), "."]
    assert cwd == target
    assert kwargs["stdout"].closed
    assert Path(kwargs["stdout"].name) == log_dir / "vscode.log"
    assert kwargs["creationflags"] == (subprocess.CREATE_NO_WINDOW if hidden else 0)


@pytest.mark.parametrize("hidden", [False, True])
@pytest.mark.parametrize("error", [PermissionError("file is locked"), OSError("cannot open log")])
def test_vscode_log_open_failure_uses_devnull(launch_setup, monkeypatch, capsys, hidden, error):
    ctx, _, _, launches = launch_setup
    ctx["args"] = [str(ctx["base_dir"])]
    if hidden:
        monkeypatch.setenv("ENGRAM_HIDDEN_LAUNCH", "1")
    real_open = builtins.open

    def locked_log(file, *args, **kwargs):
        if Path(file).name == "vscode.log":
            raise error
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", locked_log)
    launcher.main(ctx)

    assert launches[0][1]["stdout"] == subprocess.DEVNULL
    if hidden:
        assert capsys.readouterr() == ("", "")


def test_unavailable_log_directory_still_launches_silently(launch_setup, monkeypatch, capsys):
    ctx, _, log_dir, launches = launch_setup
    monkeypatch.setenv("ENGRAM_HIDDEN_LAUNCH", "1")
    log_dir.parent.mkdir(parents=True)
    log_dir.write_text("blocks directory creation", encoding="utf-8")

    launcher.main(ctx)

    assert launches[0][1]["stdout"] == subprocess.DEVNULL
    assert capsys.readouterr() == ("", "")


def test_hidden_spawn_failure_closes_log_and_logs_error(launch_setup, monkeypatch, capsys):
    ctx, _, log_dir, _ = launch_setup
    monkeypatch.setenv("ENGRAM_HIDDEN_LAUNCH", "1")
    outputs = []

    def fail_spawn(*args, **kwargs):
        outputs.append(kwargs["stdout"])
        raise OSError("spawn failed")

    monkeypatch.setattr(subprocess, "Popen", fail_spawn)
    with pytest.raises(SystemExit) as exc:
        launcher.main(ctx)

    assert exc.value.code == 1
    assert outputs[0].closed
    assert capsys.readouterr() == ("", "")
    start_log, = log_dir.glob("start_*.log")
    assert "spawn failed" in start_log.read_text(encoding="utf-8")


def test_hidden_unexpected_launch_error_is_logged_then_raised(launch_setup, monkeypatch, capsys):
    """Hidden mode has no console: an unexpected error (e.g. a missing workspace folder) must reach start_*.log."""
    ctx, _, log_dir, _ = launch_setup
    monkeypatch.setenv("ENGRAM_HIDDEN_LAUNCH", "1")

    def missing_folder(path):
        raise FileNotFoundError(f"workspace folder is missing: {path}")

    monkeypatch.setattr(launcher.os, "chdir", missing_folder)
    with pytest.raises(FileNotFoundError):
        launcher.main(ctx)

    assert capsys.readouterr() == ("", "")
    start_log, = log_dir.glob("start_*.log")
    assert "[Error] Launch failed: FileNotFoundError: workspace folder is missing" in start_log.read_text(encoding="utf-8")


def test_terminal_no_args_keeps_sandbox_and_child_exit_code(launch_setup, monkeypatch, capsys):
    ctx, _, _, launches = launch_setup
    shells = []

    def shell(argv, **kwargs):
        assert launches[0][1]["stdout"].closed
        shells.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, returncode=7)

    monkeypatch.setattr(subprocess, "run", shell)
    with pytest.raises(SystemExit) as exc:
        launcher.main(ctx)

    assert exc.value.code == 7
    assert len(shells) == 1
    assert shells[0][0] == ["cmd", "/k"]
    assert shells[0][1]["env"] == launches[0][1]["env"]
    assert launches[0][1]["creationflags"] == 0
    assert "[Sandbox] Ready" in capsys.readouterr().out


def test_hidden_missing_vscode_does_not_start_shell(launch_setup, monkeypatch, capsys):
    ctx, vscode, log_dir, launches = launch_setup
    monkeypatch.setenv("ENGRAM_HIDDEN_LAUNCH", "1")
    vscode.unlink()

    launcher.main(ctx)

    assert launches == []
    assert capsys.readouterr() == ("", "")
    start_log, = log_dir.glob("start_*.log")
    assert "VS Code not found" in start_log.read_text(encoding="utf-8")


def test_hidden_invalid_target_logs_without_printing(launch_setup, monkeypatch, capsys):
    ctx, _, log_dir, launches = launch_setup
    monkeypatch.setenv("ENGRAM_HIDDEN_LAUNCH", "1")
    ctx["args"] = [str(ctx["base_dir"] / "missing target")]

    with pytest.raises(SystemExit) as exc:
        launcher.main(ctx)

    assert exc.value.code == 2
    assert launches == []
    assert capsys.readouterr() == ("", "")
    start_log, = log_dir.glob("start_*.log")
    assert "Path not found" in start_log.read_text(encoding="utf-8")
