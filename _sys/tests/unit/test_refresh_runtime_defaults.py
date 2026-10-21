"""Release discovery must be complete before any tracked declaration changes."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from tools import refresh_runtime_defaults as refresh


def fixture_defaults():
    data = json.loads((Path(__file__).resolve().parents[3] / '_sys/defaults/runtimes.json').read_text())
    data['runtimes']['python'].update(version='3.14.5', url='https://www.python.org/ftp/python/3.14.5/python-3.14.5-embed-amd64.zip')
    return data


def fake_discover(name, cfg):
    result = dict(status='ok', latest_version=cfg['version'], url=cfg['url'])
    if name == 'python':
        result.update(latest_version='3.15.1', latest_patch_by_cycle={'3.14': '3.14.9'})
    return result


@pytest.mark.parametrize('state,version', [('ok', '3.15.1'), ('blocked', '3.14.9')])
def test_python_selection_and_all_five_fresh_hashes(state, version):
    original = fixture_defaults()
    proposed, reasons = refresh.build_defaults(original, discover=fake_discover,
        preflight=lambda *a: SimpleNamespace(state=state, reason='no compatible wheels'),
        digest=lambda url: hashlib.sha256(url.encode()).hexdigest())
    assert proposed['runtimes']['python']['version'] == version
    assert bool(reasons) == (state == 'blocked')
    for cfg in proposed['runtimes'].values():
        assert cfg['sha256'] == hashlib.sha256(cfg['url'].encode()).hexdigest()
    assert proposed['tools'] == original['tools']
    again, _ = refresh.build_defaults(proposed, discover=fake_discover,
        preflight=lambda *a: SimpleNamespace(state=state, reason='no compatible wheels'),
        digest=lambda url: hashlib.sha256(url.encode()).hexdigest())
    assert again == proposed


@pytest.mark.parametrize('failure', ['discovery', 'preflight', 'checksum'])
def test_incomplete_refresh_writes_nothing(tmp_path, failure):
    source = tmp_path / 'runtimes.json'
    source.write_text(json.dumps(fixture_defaults()))
    before = source.read_bytes()
    def discover(name, cfg):
        result = fake_discover(name, cfg)
        if failure == 'discovery':
            result.update(status='error', detail='network unavailable')
        if failure == 'checksum':
            result.update(checksum_algo='sha256', checksum_value='0' * 64)
        return result
    with pytest.raises(ValueError, match='unverified|checksum mismatch'):
        refresh.refresh_file(source, discover=discover,
            preflight=lambda *a: SimpleNamespace(state='unverifiable' if failure == 'preflight' else 'ok', reason='network'),
            digest=lambda url: '1' * 64)
    assert source.read_bytes() == before


def test_node_discovery_uses_lts(monkeypatch):
    calls = []
    monkeypatch.setattr(refresh.version_resolver, 'resolve_latest', lambda **kw: calls.append(kw) or {})
    refresh.discover('nodejs', fixture_defaults()['runtimes']['nodejs'])
    assert calls[0]['provider'] == 'nodejs_lts'
    assert calls[0]['force_refresh'] is True


def test_python_release_discovery_adds_embed_url(monkeypatch):
    monkeypatch.setattr(refresh.version_resolver, 'resolve_latest', lambda **kw:
        dict(status='ok', latest_version='3.15.1', latest_patch_by_cycle={'3.14': '3.14.9'}))
    result = refresh.discover('python', fixture_defaults()['runtimes']['python'])
    assert result['url'] == 'https://www.python.org/ftp/python/3.15.1/python-3.15.1-embed-amd64.zip'


def test_download_outage_after_selection_writes_nothing(tmp_path):
    source = tmp_path / 'runtimes.json'
    source.write_text(json.dumps(fixture_defaults()))
    before = source.read_bytes()
    calls = []
    def digest(url):
        calls.append(url)
        if len(calls) == 2:
            raise OSError('network unavailable')
        return '1' * 64
    with pytest.raises(OSError, match='network unavailable'):
        refresh.refresh_file(source, discover=fake_discover,
            preflight=lambda *a: SimpleNamespace(state='ok'), digest=digest)
    assert source.read_bytes() == before
