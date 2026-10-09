"""EN-GAP-P1-007 step 2: production batch launchers, without quoting retries.

Uses unittest so this can also run directly without pytest. A fresh installation
needs only engram.cmd, core/*.bat, version.json and static help. Dispatch's
missing-runtime exit (1) is intentional and checked against its exact diagnostic;
no Python/dispatch stub, bootstrap, backup write, or runtime installation is used.
Double quotes are illegal in Windows directory names and are tested as arguments.
Each invocation supplies an explicit, pre-quoted cmd.exe command string.
The ASCII control checks ordinary operations before any candidate is judged.
Outer expansion is disabled; paths travel through an environment variable to
avoid percent expansion by the harness. Quotes inside arguments are doubled.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import uuid


REPO_ROOT = Path(__file__).resolve().parents[3]
CASES = {
    "control": "control_ascii",
    "spaces": "name with spaces",
    "korean": "한글 설치 경로",
    "ampersand": "name & ampersand",
    "ampersand_unspaced": "name&payload",
    "percent": "name % percent",
    "percent_expansion": "name %ENGRAM_BATCH_TRAP%",
    "caret": "name ^ caret",
    "exclamation": "name !ENGRAM_BATCH_TRAP!",
    "paren_open": "name ( open",
    "paren_close": "name ) close",
    "parens_both": "name (parens)",
    "single_quote": "name ' quote",
    "combo": "combo & (100% ^ 'val') ! 한글",
}
BATCH_ERRORS = (
    "is not recognized", "was unexpected at",
    "the syntax of the command is incorrect",
)
MARKER = "batch_injected.txt"


@contextmanager
def _temporary_root():
    # Ordinary inherited permissions: restrictive tempfile ACLs can prevent the
    # child cmd.exe from reading its launchers in a managed Windows workspace.
    path = REPO_ROOT / ("engram_batch_" + uuid.uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


def _copy_launchers(root: Path) -> None:
    core = root / "_sys" / "core"
    core.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "engram.cmd", root)
    for source in (REPO_ROOT / "_sys" / "core").glob("*.bat"):
        shutil.copy2(source, core)
    shutil.copy2(REPO_ROOT / "_sys/core/version.json", core)
    shutil.copytree(REPO_ROOT / "_sys/core/help", core / "help")


@unittest.skipUnless(os.name == "nt", "requires real Windows cmd.exe")
class TestSpecialCharPathsBatch(unittest.TestCase):
    def check_case(self, name: str) -> None:
        failures = []
        version = json.loads((REPO_ROOT / "_sys/core/version.json").read_text(
            encoding="utf-8"))["version"]
        with _temporary_root() as temporary:
            parent = Path(temporary)
            root = parent / name
            _copy_launchers(root)
            env = os.environ.copy()
            for key in tuple(env):
                if key.upper().startswith("ENGRAM_"):
                    del env[key]
            env["ENGRAM_BATCH_TRAP"] = "EXPANDED_PATH_DEFECT"
            # backup has no --dry-run contract: use its read-only static help.
            # Direct dispatch also exercises the REAL core batch, with no runtime.
            operations = (
                ("help", "engram.cmd", ["help"], 0, "engram <command>"),
                ("version", "engram.cmd", ["--version"], 0, f"Engram {version}"),
                ("backup_help", "engram.cmd", ["backup", "--help"], 0,
                 "Usage: engram backup"),
                ("dispatch", "_sys/core/dispatch.bat", ["backup", "--help"], 1,
                 "Portable environment not initialized."),
                ("ampersand_payload", "engram.cmd",
                 ["help", f"missing & echo injected>{MARKER} & rem"], 2,
                 "Unknown command"),
                ("quote_payload", "engram.cmd",
                 ["help", f'missing" & echo injected>{MARKER} & rem "'], 2,
                 "Unknown command"),
            )
            for delayed in ("off",):
                for absolute in (False, True):
                    for label, launcher, args, expected_code, expected_text in operations:
                        if name == CASES["control"] and label.endswith("payload"):
                            continue
                        target = str(root / launcher) if absolute else launcher.replace("/", "\\")
                        env["BATCH_TARGET"] = target
                        quoted_args = " ".join('"' + arg.replace('"', '""') + '"'
                                               for arg in args)
                        command = '""%BATCH_TARGET%" ' + quoted_args + '"'
                        argv = ('"' + env.get("COMSPEC", "cmd.exe") +
                                '" /d /s /v:off /c ' + command)
                        identity = f"{label}/{'absolute' if absolute else 'relative'}/delayed_{delayed}"
                        try:
                            result = subprocess.run(
                                argv, cwd=root, env=env, shell=False,
                                capture_output=True, text=True, encoding="mbcs",
                                errors="replace", timeout=30,
                            )
                        except subprocess.TimeoutExpired as exc:
                            failures.append(f"{identity}: timeout: {exc}")
                            continue
                        output = result.stdout + result.stderr
                        problems = []
                        if result.returncode != expected_code:
                            problems.append(f"exit {result.returncode}, expected {expected_code}")
                        if expected_text not in output:
                            problems.append(f"missing {expected_text!r}")
                        problems.extend(f"batch error: {text}" for text in BATCH_ERRORS
                                        if text in output.lower())
                        # Root, caller directory, and descendants cover changes of cwd.
                        markers = list(parent.rglob(MARKER))
                        if markers:
                            problems.append(f"injected side-effect file: {markers}")
                        if problems:
                            failures.append(f"{identity}: {'; '.join(problems)}\n"
                                            f"argv={argv!r}\n{output}")
                        # Record the injection before removing its marker; keep
                        # subsequent invocations independent of earlier defects.
                        for marker in markers:
                            marker.unlink()
            self.assertFalse(bool(failures), "Candidate defect(s) for exact directory name "
                             f"{name!r}:\n" + "\n".join(failures))


def _make_test(name: str):
    def test(self):
        self.check_case(name)
    return test


for _case_id, _name in CASES.items():
    setattr(TestSpecialCharPathsBatch, f"test_batch_{'00_control' if _case_id == 'control' else _case_id}", _make_test(_name))


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    control = runner.run(unittest.TestSuite([
        TestSpecialCharPathsBatch("test_batch_00_control")]))
    if not control.wasSuccessful():
        raise SystemExit("CONTROL FAILED: repair harness before judging candidates")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestSpecialCharPathsBatch)
    candidates = unittest.TestSuite(test for test in suite
                                   if test._testMethodName != "test_batch_00_control")
    raise SystemExit(not runner.run(candidates).wasSuccessful())
