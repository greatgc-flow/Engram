"""Mandatory installed-artifact commands shared by both clean-room providers."""
import json
from pathlib import Path


def commands(root):
    suite = json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))
    return [[str(Path(root) / check['path']), *check['args']] for check in suite]


def run_checks(root, *, runner, env):
    for command in commands(root):
        if not Path(command[0]).is_file():
            raise ValueError(f"candidate missing {command[0]}")
        runner(command, cwd=root, env=env)
