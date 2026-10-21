"""Invalid declarations must stop batch bootstrap before downloads/install."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('declaration', [None, '{broken', '{}', json.dumps({'runtimes': {'python': {
    'version': 'bad', 'url': 'http://invalid', 'get_pip_url': 'https://bootstrap.pypa.io/get-pip.py'}}}),
    *[json.dumps({'runtimes': {'python': {
        'version': '3.14.5', 'url': 'https://www.python.org/python.zip',
        'get_pip_url': 'https://bootstrap.pypa.io/get-pip.py'} | {field: bad}}})
      for field, bad in [('version', None), ('version', ['3.14.5']), ('url', None),
                         ('get_pip_url', ''), ('sha256', 'invalid')]]])
def test_invalid_declaration_fails_before_network(tmp_path, declaration):
    core = tmp_path / '_sys/core'
    core.mkdir(parents=True)
    shutil.copy2(ROOT / '_sys/core/bootstrap.bat', core / 'bootstrap.bat')
    if declaration is not None:
        (core.parent / 'runtimes.json').write_text(declaration)
    # A poisoned inherited environment must never supply missing fields.
    env = dict(os.environ, CI='true', PY_VER='9.9.9', PY_URL='https://invalid/',
               GET_PIP_URL='https://invalid/', PY_SHA256='0' * 64)
    marker = tmp_path / 'network-called'
    (tmp_path / 'curl.bat').write_text('@echo off\necho called>network-called\nexit /b 99\n')
    env['PATH'] = str(tmp_path) + os.pathsep + env['PATH']
    cp = subprocess.run(['cmd', '/d', '/c', str(core / 'bootstrap.bat'), '--skip-update'],
                        cwd=tmp_path, env=env, capture_output=True, text=True, errors="replace", timeout=30)
    assert cp.returncode != 0
    assert 'declaration' in (cp.stdout + cp.stderr).lower()
    assert not marker.exists()
    assert not (core.parent / 'env').exists()


def test_malformed_live_never_uses_valid_defaults(tmp_path):
    core = tmp_path / '_sys/core'
    core.mkdir(parents=True)
    shutil.copy2(ROOT / '_sys/core/bootstrap.bat', core / 'bootstrap.bat')
    (core.parent / 'defaults').mkdir()
    shutil.copy2(ROOT / '_sys/defaults/runtimes.json', core.parent / 'defaults/runtimes.json')
    (core.parent / 'runtimes.json').write_text('{bad')
    cp = subprocess.run(['cmd', '/d', '/c', str(core / 'bootstrap.bat'), '--skip-update'],
                        cwd=tmp_path, env=dict(os.environ, CI='true'), capture_output=True, text=True, errors="replace", timeout=30)
    assert cp.returncode != 0
    assert 'declaration' in (cp.stdout + cp.stderr).lower()
    assert (core.parent / 'runtimes.json').read_text() == '{bad'
    assert not (core.parent / 'env').exists()


@pytest.mark.parametrize('live', [False, True])
def test_valid_defaults_seed_and_live_wins(tmp_path, live):
    core = tmp_path / '_sys/core'
    core.mkdir(parents=True)
    shutil.copy2(ROOT / '_sys/core/bootstrap.bat', core / 'bootstrap.bat')
    defaults = json.loads((ROOT / '_sys/defaults/runtimes.json').read_text())
    (core.parent / 'defaults').mkdir()
    (core.parent / 'defaults/runtimes.json').write_text(json.dumps(defaults))
    expected = defaults['runtimes']['python']['version']
    if live:
        defaults['runtimes']['python'].update(version='3.14.1',
            url='https://www.python.org/ftp/python/3.14.1/python-3.14.1-embed-amd64.zip')
        (core.parent / 'runtimes.json').write_text(json.dumps(defaults))
        expected = '3.14.1'
    (tmp_path / 'curl.bat').write_text('@echo off\necho %*>network-called\nexit /b 99\n')
    env = dict(os.environ, CI='true', PY_VER='9.9.9', PY_URL='https://invalid/')
    env['PATH'] = str(tmp_path) + os.pathsep + env['PATH']
    cp = subprocess.run(['cmd', '/d', '/c', str(core / 'bootstrap.bat'), '--skip-update'],
                        cwd=tmp_path, env=env, capture_output=True, text=True, errors="replace", timeout=30)
    assert expected in cp.stdout
    assert expected in (tmp_path / 'network-called').read_text()
    assert json.loads((core.parent / 'runtimes.json').read_text()) == defaults
