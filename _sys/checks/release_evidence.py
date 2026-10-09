"""Freeze release asset digests and fail closed on Sandbox evidence.

Candidate schema: tag, commit, candidate_sha256s (relative asset name -> SHA256).
Evidence schema: status=PASS and the identical candidate_sha256s mapping.
Sandbox provider, runner_environment, workflow_run_id and image are required.
--policy defaults to the repository release_policy.json and is always enforced.
All evidence requires explicit-false flags and current promotion run identity.
Upgrade and WinGet evidence are required and must include both flags as exactly false.
--no-winget-evidence is an explicit legacy/test-only opt-out.
--no-upgrade-evidence is a legacy/test-only opt-out. Provenance comes from
RELEASE_TAG/GITHUB_REF_NAME and GITHUB_SHA, with local Git fallbacks.
Existing candidate files are never overwritten; rebuilding needs a new path.
This offline gate checks evidence consistency, not evidence authenticity.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess


DEFAULT_POLICY = Path(__file__).resolve().parents[2] / "release_policy.json"
PROVIDER_ENVIRONMENTS = {
    "windows-sandbox": "self-hosted",
    "hosted-ephemeral-vm": "github-hosted",
}


class Hold(ValueError):
    """A release cannot be promoted."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Hold("duplicate JSON key")
        result[key] = value
    return result


def _read(path):
    with Path(path).open(encoding="utf-8") as stream:
        value = json.load(stream, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise Hold("JSON document must be an object")
    return value


def _hashes(value):
    if not isinstance(value, dict) or not value:
        raise Hold("missing or empty candidate_sha256s")
    for name, digest in value.items():
        if (not isinstance(name, str) or not name
                or "\\" in name or ":" in name
                or PurePosixPath(name).is_absolute()
                or any(part in ("", ".", "..") for part in name.split("/"))):
            raise Hold("invalid asset path")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise Hold("invalid asset SHA256")
    return value


def _identity(candidate):
    tag = candidate.get("tag")
    commit = candidate.get("commit")
    if not isinstance(tag, str) or not tag.strip() or any(c.isspace() for c in tag):
        raise Hold("missing or invalid release tag")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", commit):
        raise Hold("missing or invalid commit")


def _git(*args):
    result = subprocess.run(
        ["git", "-c", f"safe.directory={Path(__file__).resolve().parents[2].as_posix()}", *args],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True, check=False, timeout=10,
    )
    if result.returncode:
        raise Hold("release provenance unavailable; set RELEASE_TAG and GITHUB_SHA")
    return result.stdout.strip()


def freeze(assets, out):
    assets = Path(assets).resolve()
    out = Path(out).absolute()
    if out.exists() or out.is_symlink():
        raise Hold("candidate already exists; use a new candidate identity")
    if not assets.is_dir():
        raise Hold("release assets directory is missing")
    if out.resolve().is_relative_to(assets):
        raise Hold("candidate output must be outside release assets")
    hashes = {}
    for path in sorted(assets.rglob("*")):
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise Hold("release assets must not contain links")
        if path.is_file():
            digest = hashlib.sha256()
            before = path.stat()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise Hold("release asset changed during freeze")
            hashes[path.relative_to(assets).as_posix()] = digest.hexdigest()
    _hashes(hashes)
    candidate = {
        "tag": os.environ.get("RELEASE_TAG") or os.environ.get("GITHUB_REF_NAME") or _git("describe", "--tags", "--exact-match", "HEAD"),
        "commit": os.environ.get("GITHUB_SHA") or _git("rev-parse", "HEAD"),
        "candidate_sha256s": hashes,
    }
    _identity(candidate)
    payload = json.dumps(candidate, sort_keys=True, indent=2) + "\n"
    # Exclusive creation prevents a second freeze from replacing this identity.
    with out.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)


def validate_evidence(evidence, hashes, label, *, run_id, run_attempt):
    """One fail-closed predicate for every promotion evidence type."""
    if evidence.get("status") != "PASS":
        raise Hold(f"{label} evidence status is not PASS")
    for flag in ("cancelled", "skipped"):
        if evidence.get(flag) is not False:
            raise Hold(f"{label} evidence is {flag} or has an invalid flag")
    if _hashes(evidence.get("candidate_sha256s")) != hashes:
        raise Hold(f"{label} evidence candidate hashes do not match exactly")
    for field, expected in (("run_id", run_id), ("run_attempt", run_attempt)):
        if not isinstance(expected, str) or not expected.isdecimal() or int(expected) < 1:
            raise Hold(f"current promotion {field} is required")
        if evidence.get(field) != expected:
            raise Hold(f"{label} evidence {field} differs from current promotion")


def verify(candidate_path, evidence_path, upgrade_evidence_path=None, *, no_upgrade_evidence=False,
           winget_evidence_path=None, no_winget_evidence=False, policy_path=DEFAULT_POLICY,
           run_id=None, run_attempt=None):
    if upgrade_evidence_path is None and not no_upgrade_evidence:
        raise Hold("upgrade evidence is required")
    if upgrade_evidence_path is not None and no_upgrade_evidence:
        raise Hold("upgrade evidence and opt-out are mutually exclusive")
    if winget_evidence_path is None and not no_winget_evidence:
        raise Hold("WinGet evidence is required")
    if winget_evidence_path is not None and no_winget_evidence:
        raise Hold("WinGet evidence and opt-out are mutually exclusive")
    run_id = run_id if run_id is not None else os.environ.get("GITHUB_RUN_ID")
    run_attempt = run_attempt if run_attempt is not None else os.environ.get("GITHUB_RUN_ATTEMPT")
    candidate = _read(candidate_path)
    _identity(candidate)
    hashes = _hashes(candidate.get("candidate_sha256s"))
    evidence = _read(evidence_path)
    policy = _read(policy_path)
    providers = policy.get("sandbox_providers")
    if (not isinstance(providers, list) or not providers
            or any(not isinstance(provider, str) or provider not in PROVIDER_ENVIRONMENTS
                   for provider in providers)):
        raise Hold("invalid sandbox provider policy")
    for field in ("provider", "runner_environment", "workflow_run_id", "image"):
        value = evidence.get(field)
        if not isinstance(value, str) or not value.strip():
            raise Hold(f"Sandbox evidence {field} is missing or invalid")
    provider = evidence["provider"]
    if provider not in providers:
        raise Hold("Sandbox evidence provider is not allowed by policy")
    if evidence["runner_environment"] != PROVIDER_ENVIRONMENTS[provider]:
        raise Hold("Sandbox evidence provider and runner_environment do not match")
    validate_evidence(evidence, hashes, "Sandbox", run_id=run_id, run_attempt=run_attempt)
    if evidence["workflow_run_id"] != run_id:
        raise Hold("Sandbox workflow_run_id differs from current promotion")
    if upgrade_evidence_path is not None:
        if not Path(upgrade_evidence_path).is_file():
            raise Hold("upgrade evidence file is missing")
        upgrade_evidence = _read(upgrade_evidence_path)
        validate_evidence(upgrade_evidence, hashes, "upgrade", run_id=run_id, run_attempt=run_attempt)
        if upgrade_evidence.get("scenarios") != {"upgrade": "PASS", "rollback": "PASS"}:
            raise Hold("upgrade evidence requires upgrade and rollback scenarios")
        if upgrade_evidence.get("updater_source") not in ("previous", "candidate"):
            raise Hold("upgrade evidence updater source is missing or invalid")
        prev_tag = upgrade_evidence.get("previous_tag")
        if not isinstance(prev_tag, str) or not prev_tag.strip() or any(c.isspace() for c in prev_tag) or prev_tag == candidate.get("tag"):
            raise Hold("upgrade evidence previous tag is missing, invalid, or matches candidate")

    if winget_evidence_path is not None:
        if not Path(winget_evidence_path).is_file():
            raise Hold('WinGet evidence file is missing')
        evidence = _read(winget_evidence_path)
        validate_evidence(evidence, hashes, "WinGet", run_id=run_id, run_attempt=run_attempt)



def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze_parser = commands.add_parser("freeze")
    freeze_parser.add_argument("--assets", required=True)
    freeze_parser.add_argument("--out", required=True)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--run-id", required=True)
    verify_parser.add_argument("--run-attempt", required=True)
    verify_parser.add_argument("--candidate", required=True)
    verify_parser.add_argument("--evidence", required=True)
    verify_parser.add_argument("--policy", default=DEFAULT_POLICY,
                               help="required provider policy (default: repository release_policy.json)")
    upgrade_options = verify_parser.add_mutually_exclusive_group()
    upgrade_options.add_argument("--upgrade-evidence", default=None)
    upgrade_options.add_argument(
        "--no-upgrade-evidence", action="store_true",
        help="legacy/test-only opt-out from required upgrade evidence",
    )
    winget_options = verify_parser.add_mutually_exclusive_group()
    winget_options.add_argument("--winget-evidence", default=None)
    winget_options.add_argument("--no-winget-evidence", action="store_true",
                               help="legacy/test-only opt-out from required WinGet evidence")
    args = parser.parse_args(argv)
    try:
        if args.command == "freeze":
            freeze(args.assets, args.out)
        else:
            verify(
                args.candidate, args.evidence, args.upgrade_evidence,
                no_upgrade_evidence=args.no_upgrade_evidence,
                winget_evidence_path=args.winget_evidence,
                no_winget_evidence=args.no_winget_evidence,
                policy_path=args.policy,
                run_id=args.run_id, run_attempt=args.run_attempt,
            )
    except (Hold, OSError, ValueError, subprocess.SubprocessError) as exc:
        reason = " ".join(str(exc).split())
        print(f"HOLD: {reason}")
        return 1
    print("PASS: candidate frozen" if args.command == "freeze" else "PASS: candidate evidence verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
