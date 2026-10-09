"""Generate the Sandbox entry from the same mandatory installed suite as hosted."""
import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from installed_artifact_suite import commands


def prepare(root):
    lines = [
        '@echo off', 'set "CI=1"', 'set "PYTHONUTF8=1"',
        'set "SRC=%SYSTEMDRIVE%\\PortableDev"',
        'set "TGT=%SYSTEMDRIVE%\\TargetEnv"',
        'set "RES=%SYSTEMDRIVE%\\TestResults"',
        'robocopy "%SRC%" "%TGT%" /MIR /XD "%SRC%\\_sys\\env" "%SRC%\\_sys\\tools" "%SRC%\\.git" "%SRC%\\_archive" "%SRC%\\workspace" node_modules pip-cache npm-cache > "%RES%\\robocopy_log.txt"',
        'if errorlevel 8 goto :failed', 'cd /d "%TGT%"',
    ]
    for command in commands(Path('.')):
        # All paths/arguments are fixed repository-owned suite data.
        lines.extend(['call ' + subprocess.list2cmdline(command) + ' >> "%RES%\\installed_suite.txt" 2>&1',
                      'if errorlevel 1 goto :failed'])
    lines.extend([
        'set "PY=%TGT%\\_sys\\env\\venv\\Scripts\\python.exe"',
        '"%PY%" -m pip install -r requirements-dev.txt >> "%RES%\\install_log.txt" 2>&1',
        'if errorlevel 1 goto :failed',
        '"%PY%" -m pytest _sys\\tests\\unit -v --junitxml="%RES%\\contract-results.xml" > "%RES%\\pytest_report.txt" 2>&1',
        'if errorlevel 1 goto :failed',
        '"%PY%" tools\\release_gate\\check_required_tests.py --report "%RES%\\contract-results.xml"',
        'if errorlevel 1 goto :failed',
        'echo PASS> "%RES%\\result.txt"', 'goto :done',
        ':failed', 'echo FAIL> "%RES%\\result.txt"', ':done',
        'shutdown /s /t 5',
    ])
    entry = Path(root) / '_sys/tests/wsb-entry.bat'
    entry.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return entry


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    prepare(parser.parse_args().root)
