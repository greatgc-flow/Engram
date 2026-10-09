"""Offline ancestry gate tests; never invoke Git."""
import importlib.util
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "tools/release_gate/check_tag_on_main.py"


def load_gate():
    spec = importlib.util.spec_from_file_location("check_tag_on_main", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("code", [0, 1, 128])
def test_tag_requires_ancestry(code):
    gate = load_gate()
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        if "rev-parse" in command:
            return subprocess.CompletedProcess(command, 0, "a" * 40 + "\n", "")
        return subprocess.CompletedProcess(command, code, "", "")
    if code == 0:
        gate.check_tag_on_main("v1.2.3", runner=runner)
    else:
        with pytest.raises(gate.Hold):
            gate.check_tag_on_main("v1.2.3", runner=runner)
    assert calls[0] == ["git", "rev-parse", "--verify", "refs/tags/v1.2.3^{commit}"]
    assert calls[1] == ["git", "merge-base", "--is-ancestor", "a" * 40, "origin/main"]


@pytest.mark.parametrize("tag", [None, "", " ", "--help", "tag with spaces"])
def test_invalid_tag_never_runs_git(tag):
    gate = load_gate()
    def runner(*args, **kwargs):
        raise AssertionError("runner must not be called")
    with pytest.raises(gate.Hold):
        gate.check_tag_on_main(tag, runner=runner)


@pytest.mark.parametrize("mode", ["missing", "malformed", "timeout", "unavailable"])
def test_unavailable_tag_holds(mode):
    gate = load_gate()
    def runner(command, **kwargs):
        if mode == "timeout":
            raise subprocess.TimeoutExpired(command, 10)
        if mode == "unavailable":
            raise FileNotFoundError("git")
        return subprocess.CompletedProcess(command, 128 if mode == "missing" else 0, "bad", "")
    with pytest.raises(gate.Hold):
        gate.check_tag_on_main("v1.2.3", runner=runner)
