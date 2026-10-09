"""Post-publication closure only; stdlib and gh, with offline fetcher seams."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

DEFAULT_POLICY = Path(__file__).resolve().parents[2] / "release_policy.json"

def read_policy(path=DEFAULT_POLICY):
    return json.loads(Path(path).read_text(encoding="utf-8"))
from urllib.parse import quote


def gh_api(endpoint):
    result = subprocess.run(['gh', 'api', endpoint], capture_output=True, text=True,
                            timeout=60, check=False)
    if result.returncode:
        raise RuntimeError(f'gh api {endpoint}: {result.stderr.strip()}')
    return json.loads(result.stdout)


def release_fetcher(repo):
    def fetch(tag):
        release = gh_api(f'repos/{repo}/releases/tags/{quote(tag, safe="")}')
        # Paginate inventory rather than trusting the embedded assets subset.
        assets, page = [], 1
        while True:
            batch = gh_api(f'repos/{repo}/releases/{release["id"]}/assets?per_page=100&page={page}')
            if not isinstance(batch, list):
                raise ValueError('invalid release assets response')
            assets.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        release['assets'] = assets
        return release
    return fetch


def fetch_winget(version):
    # Contents on the upstream default branch prove merge; only explicit 404 is pending.
    path = f'manifests/g/greatgc-flow/Engram/{version}/greatgc-flow.Engram.yaml'
    endpoint = f'repos/microsoft/winget-pkgs/contents/{quote(path, safe="/")}'
    result = subprocess.run(['gh', 'api', endpoint], capture_output=True, text=True,
                            timeout=60, check=False)
    if result.returncode:
        try:
            missing = str(json.loads(result.stdout).get('status')) == '404'
        except (ValueError, AttributeError):
            missing = False
        if missing:
            return 'pending'
        raise RuntimeError(f'WinGet API error: {result.stderr.strip()}')
    manifest = json.loads(result.stdout)
    if manifest.get('type') != 'file' or manifest.get('path') != path or not manifest.get('sha'):
        raise ValueError('invalid upstream manifest response')
    return 'available'


def check_closure(candidate, *, fetch_release, fetch_winget, now=None, pending_days=None):
    if pending_days is None:
        pending_days = read_policy()["winget_pending_days"]
    now = now or datetime.now(timezone.utc)
    evidence = {'status': 'DRIFT', 'tag': candidate.get('tag'),
                'candidate_sha256s': candidate.get('candidate_sha256s', {}),
                'published_digests': {}, 'checked_at': now.isoformat(),
                'winget': 'unknown', 'recheck': 'weekly post-release-closure.yml or workflow_dispatch'}
    try:
        tag = candidate.get('tag')
        if not isinstance(tag, str) or not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?', tag):
            raise ValueError('invalid version tag')
        hashes = evidence['candidate_sha256s']
        if not isinstance(hashes, dict) or not hashes:
            raise ValueError('empty candidate hashes')
        expected = {}
        for path, digest in hashes.items():
            if (not isinstance(path, str) or not path or '\\' in path or ':' in path
                    or PurePosixPath(path).is_absolute()
                    or any(part in ('', '.', '..') for part in path.split('/'))
                    or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)):
                raise ValueError('invalid candidate asset/hash')
            name = PurePosixPath(path).name
            if name in expected:
                raise ValueError('candidate asset basename collision')
            expected[name] = digest
        release = fetch_release(tag)
        if release.get('draft') is not False or release.get('tag_name') != tag or not release.get('published_at'):
            raise ValueError('release is not published under the candidate tag')
        published_at = datetime.fromisoformat(release['published_at'].replace('Z', '+00:00'))
        if published_at.tzinfo is None or published_at > now:
            raise ValueError('invalid publication time')
        evidence['published_at'] = published_at.isoformat()
        actual = evidence['published_digests']
        for asset in release['assets']:
            name, digest = asset['name'], asset.get('digest')
            if name in actual:
                raise ValueError('duplicate published asset name')
            actual[name] = digest
            if asset.get('state') != 'uploaded' or not isinstance(digest, str) or not re.fullmatch('sha256:[0-9a-f]{64}', digest):
                raise ValueError(f'missing/invalid published SHA256: {name}')
            actual[name] = digest.removeprefix('sha256:')
        if actual != expected:
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            replaced = sorted(name for name in expected.keys() & actual.keys() if expected[name] != actual[name])
            raise ValueError(f'published assets differ: missing={missing}, extra={extra}, replaced={replaced}')
        winget = fetch_winget(tag[1:])
        evidence['winget'] = winget
        deadline = published_at + timedelta(days=pending_days)
        evidence['pending_deadline'] = deadline.isoformat()
        if winget == 'available':
            evidence['status'] = 'CLOSED'
        elif winget == 'pending' and now < deadline:
            evidence['status'] = 'OPEN_PENDING'
        elif winget == 'pending':
            raise ValueError('WinGet pending deadline exceeded')
        else:
            raise ValueError('unknown WinGet availability')
        evidence['summary'] = f'{evidence["status"]}: {tag}; published hashes match; WinGet {winget}'
    except Exception as exc:
        evidence['status'] = 'DRIFT'
        evidence['summary'] = f'DRIFT: {evidence["tag"]}; {exc}. Investigate release provenance; attach post_release_closure.json.'
    return evidence


def exit_code(evidence):
    return 0 if evidence['status'] in ('CLOSED', 'OPEN_PENDING') else 1


def check_ledger(candidates_dir, results_dir, repo, *, run=subprocess.run, summary_path=None, policy_path=DEFAULT_POLICY):
    """Bound each candidate independently and retain DRIFT on timeout."""
    candidates = sorted(Path(candidates_dir).glob('*.json'))
    if not candidates:
        raise ValueError('DRIFT: no frozen candidates; recover the promotion artifact and rerun')
    failed = False
    for candidate in candidates:
        out = Path(results_dir) / candidate.stem / 'post_release_closure.json'
        try:
            result = run([sys.executable, str(Path(__file__).resolve()), '--candidate', str(candidate),
                          '--repo', repo, '--out', str(out), '--policy', str(policy_path)],
                         capture_output=True, text=True, timeout=180)
            summary = result.stdout + result.stderr
            failed |= result.returncode != 0
        except subprocess.TimeoutExpired:
            frozen = json.loads(candidate.read_text(encoding='utf-8-sig'))
            summary = f'DRIFT: {frozen.get("tag")}; candidate closure timed out; recheck this candidate'
            evidence = dict(status='DRIFT', tag=frozen.get('tag'),
                            candidate_sha256s=frozen.get('candidate_sha256s', {}), published_digests={},
                            checked_at=datetime.now(timezone.utc).isoformat(), summary=summary,
                            recheck='weekly post-release-closure.yml or workflow_dispatch')
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
            failed = True
        print(summary)
        if summary_path:
            with Path(summary_path).open('a', encoding='utf-8') as stream:
                stream.write(summary + '\n')
    return int(failed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', default=DEFAULT_POLICY, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        candidate = json.loads(args.candidate.read_text(encoding='utf-8-sig'))
        if not isinstance(candidate, dict):
            raise ValueError('candidate must be an object')
        evidence = check_closure(candidate, fetch_release=release_fetcher(args.repo), fetch_winget=fetch_winget,
                                 pending_days=read_policy(args.policy)["winget_pending_days"])
    except Exception as exc:
        evidence = {'status': 'DRIFT', 'candidate_sha256s': {}, 'published_digests': {},
                    'checked_at': datetime.now(timezone.utc).isoformat(), 'summary': f'DRIFT: {exc}'}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(evidence['summary'])
    return exit_code(evidence)


if __name__ == '__main__':
    raise SystemExit(main())
