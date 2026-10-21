"""Refresh tracked release defaults only; hosted bootstrap/pytest validates them."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '_sys'))
sys.path.insert(0, str(ROOT))
from _sys.checks.check_tool_updates import discover_release_runtime as discover, version_resolver
from core.baseline_packages import runtime_pins
from core.repair import _python_minor_preflight


def preflight(version, url):
    return _python_minor_preflight(version, url, managed_python=Path(sys.executable),
                                   specs=tuple(runtime_pins().values()))


def digest(url):
    value = hashlib.sha256()
    request = urllib.request.Request(url, headers={'User-Agent': 'Engram-runtime-refresh'})
    with urllib.request.urlopen(request, timeout=60) as response:
        while chunk := response.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def build_defaults(original, *, discover=discover, preflight=preflight, digest=digest):
    proposed = copy.deepcopy(original)
    reasons = []
    for name in ('python', 'nodejs', 'git', 'vscode', 'pwsh'):
        cfg = proposed['runtimes'][name]
        found = discover(name, cfg)
        if found.get('status') != 'ok' or not found.get('latest_version') or not found.get('url'):
            raise ValueError(f"unverified {name}: {found.get('detail', found.get('status'))}")
        version, url = found['latest_version'], found['url']
        fallback = False
        if name == 'python':
            url = f'https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip'
            readiness = preflight(version, url)
            if readiness.state == 'unverifiable':
                raise ValueError(f'unverified Python: {readiness.reason}')
            if readiness.state == 'blocked':
                cycle = '.'.join(cfg['version'].split('.')[:2])
                version = found.get('latest_patch_by_cycle', {}).get(cycle)
                if not version:
                    raise ValueError('unverified Python: no current-minor patch discovered')
                reasons.append(f'Python fallback to {version}: {readiness.reason}')
                url = f'https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip'
                fallback = True
            elif readiness.state != 'ok':
                raise ValueError(f'unverified Python readiness: {readiness.state}')
        actual = digest(url)
        expected = found.get('checksum_value') if found.get('checksum_algo') == 'sha256' else None
        if expected and not fallback and actual.lower() != expected.lower():
            raise ValueError(f'{name} checksum mismatch')
        cfg.update(version=version, url=url, sha256=actual)
    return proposed, reasons


def refresh_file(path, **kwargs):
    path = Path(path)
    original = json.loads(path.read_text(encoding='utf-8'))
    proposed, reasons = build_defaults(original, **kwargs)
    if proposed != original:
        temporary = path.with_name(path.name + '.tmp')
        try:
            temporary.write_text(json.dumps(proposed, indent=4, ensure_ascii=False) + '\n', encoding='utf-8')
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return proposed, reasons


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--body-file', type=Path)
    args = parser.parse_args(argv)
    try:
        proposed, reasons = refresh_file(ROOT / '_sys/defaults/runtimes.json')
        lines = ['Refresh latest validated runtime defaults.', '']
        for name, cfg in proposed['runtimes'].items():
            lines.append(f"- {name}: {cfg['version']} (sha256 `{cfg['sha256']}`)")
        lines += ['', *reasons, '', 'Validation: bootstrap, consistency checks, full unit suite and required contracts.',
                  'Run: ' + os.environ.get('ENGRAM_REFRESH_RUN_URL', 'local; hosted validation still required')]
        body = '\n'.join(lines) + '\n'
        if args.body_file:
            args.body_file.write_text(body, encoding='utf-8')
        print(body)
        return 0
    except Exception as exc:
        print(f'unverified refresh: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
