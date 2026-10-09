"""Exact-candidate WinGet smoke. Missing CLI or any incomplete check means HOLD."""
import argparse
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import zipfile

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "release_evidence_checks", Path(__file__).resolve().parents[2] / "_sys/checks/release_evidence.py"
)
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
Hold = base.Hold


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
    if result.returncode != 0:
        raise Hold(f'{args[0]} {args[1]} exited {result.returncode}: {result.stderr}')
    return result.stdout.strip()


def snapshot(root):
    return {p.relative_to(root).as_posix(): digest(p) for p in root.rglob('*') if p.is_file()}


def smoke(candidate, assets, install_root, user_data, run=command):
    hashes = base._hashes(candidate.get('candidate_sha256s'))
    base._identity(candidate)
    for path in assets.rglob('*'):
        if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
            raise Hold('candidate contains links')
    if snapshot(assets) != hashes:
        raise Hold('candidate asset hashes differ')
    archives = list(assets.glob('*.zip'))
    installers = list((assets / 'manifests').rglob('*.installer.yaml'))
    if len(archives) != 1 or len(installers) != 1:
        raise Hold('expected one ZIP and installer manifest')
    archive, installer = archives[0], installers[0]
    text = installer.read_text(encoding='utf-8')
    def scalar(key):
        values = re.findall(rf'^\s*{key}:\s*(\S+)\s*$', text, re.M)
        if len(values) != 1:
            raise Hold(f'expected one {key}')
        return values[0]
    version, package = scalar('PackageVersion'), scalar('PackageIdentifier')
    if scalar('InstallerSha256').lower() != digest(archive):
        raise Hold('installer hash differs from candidate ZIP')
    scalar('InstallerUrl')
    if install_root.exists():
        raise Hold('install location already exists')
    alias = Path(os.environ['LOCALAPPDATA']) / 'Microsoft/WinGet/Links/engram.exe'
    if alias.exists() or alias.is_symlink():
        raise Hold('engram command alias already exists')
    run(['winget', '--version'])  # absence is HOLD, never skipped
    run(['winget', 'settings', '--enable', 'LocalManifestFiles'])
    with tempfile.TemporaryDirectory(prefix='engram-winget-') as temporary:
        manifests = Path(temporary) / 'manifests'
        shutil.copytree(installer.parent, manifests)
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(assets)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}/{archive.name}'
            (manifests / installer.name).write_text(re.sub(r'(?m)^(\s*InstallerUrl:\s*).+$', lambda m: m[1] + url, text), encoding='utf-8')
            run(['winget', 'install', '--manifest', str(manifests), '--scope', 'user', '--location', str(install_root),
                 '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity'])
            with zipfile.ZipFile(archive) as payload:
                for member in payload.infolist():
                    if member.is_dir():
                        continue
                    target = (install_root / member.filename).resolve()
                    if not target.is_relative_to(install_root.resolve()):
                        raise Hold('unsafe ZIP member')
                    if not target.is_file() or digest(target) != hashlib.sha256(payload.read(member)).hexdigest():
                        raise Hold(f'installed file differs: {member.filename}')
            user_data.mkdir(parents=True, exist_ok=True)
            marker = user_data / 'winget-smoke-preservation.bin'
            if marker.exists():
                raise Hold('user data sentinel already exists')
            marker.write_bytes(b'Engram WinGet preservation\x00\xff')
            before = snapshot(user_data)
            if not alias.exists() or not os.path.samefile(alias, install_root / 'Engram.exe'):
                raise Hold('engram command alias does not target candidate')
            if run([str(alias), '--version']) != f'Engram {version} (Portable Dev Runtime)':
                raise Hold('installed version differs from candidate')
            run(['winget', 'uninstall', '--id', package, '--exact', '--scope', 'user', '--disable-interactivity'])
            if any(p.is_file() and not p.is_relative_to(user_data) for p in install_root.rglob('*')):
                raise Hold('program files remain after uninstall')
            if alias.exists() or alias.is_symlink():
                raise Hold('engram command alias remains after uninstall')
            if snapshot(user_data) != before:
                raise Hold('user data changed')
            if snapshot(assets) != hashes:
                raise Hold('frozen assets changed')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'assets', 'install-root', 'user-data', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args(argv)
    evidence = {'status': 'HOLD', 'candidate_sha256s': {}, 'cancelled': False, 'skipped': False,
                'run_id': os.environ.get('GITHUB_RUN_ID'), 'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT')}
    try:
        candidate = base._read(args.candidate)
        evidence['candidate_sha256s'] = candidate.get('candidate_sha256s', {})
        smoke(candidate, args.assets, args.install_root, args.user_data)
        evidence['status'] = 'PASS'
    except (OSError, ValueError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        evidence['reason'] = str(exc)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(evidence['status'] + ': ' + evidence.get('reason', 'WinGet candidate smoke complete'))
    return 0 if evidence['status'] == 'PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
