"""Freeze release asset digests and fail closed on Sandbox evidence.

Candidate schema: tag, commit, candidate_sha256s (relative asset name -> SHA256).
Evidence schema: status=PASS and the identical candidate_sha256s mapping.
Sandbox cancelled/skipped flags, when present, must be exactly false.
Upgrade evidence is required and must include both flags as exactly false.
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


def verify(candidate_path, evidence_path, upgrade_evidence_path=None, *, no_upgrade_evidence=False):
    if upgrade_evidence_path is None and not no_upgrade_evidence:
        raise Hold("upgrade evidence is required")
    if upgrade_evidence_path is not None and no_upgrade_evidence:
        raise Hold("upgrade evidence and opt-out are mutually exclusive")
    candidate = _read(candidate_path)
    _identity(candidate)
    hashes = _hashes(candidate.get("candidate_sha256s"))
    evidence = _read(evidence_path)
    if evidence.get("status") != "PASS":
        raise Hold("Sandbox evidence status is not PASS")
    for flag in ("cancelled", "skipped"):
        if flag in evidence and evidence[flag] is not False:
            raise Hold(f"Sandbox evidence is {flag} or has an invalid flag")
    if _hashes(evidence.get("candidate_sha256s")) != hashes:
        raise Hold("Sandbox evidence candidate hashes do not match exactly")
    if upgrade_evidence_path is not None:
        if not Path(upgrade_evidence_path).is_file():
            raise Hold("upgrade evidence file is missing")
        upgrade_evidence = _read(upgrade_evidence_path)
        if upgrade_evidence.get("status") != "PASS":
            raise Hold("upgrade evidence status is not PASS")
        for flag in ("cancelled", "skipped"):
            if upgrade_evidence.get(flag) is not False:
                raise Hold(f"upgrade evidence is {flag} or has an invalid flag")
        if _hashes(upgrade_evidence.get("candidate_sha256s")) != hashes:
            raise Hold("upgrade evidence candidate hashes do not match exactly")
        prev_tag = upgrade_evidence.get("previous_tag")
        if not isinstance(prev_tag, str) or not prev_tag.strip() or any(c.isspace() for c in prev_tag) or prev_tag == candidate.get("tag"):
            raise Hold("upgrade evidence previous tag is missing, invalid, or matches candidate")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze_parser = commands.add_parser("freeze")
    freeze_parser.add_argument("--assets", required=True)
    freeze_parser.add_argument("--out", required=True)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--candidate", required=True)
    verify_parser.add_argument("--evidence", required=True)
    upgrade_options = verify_parser.add_mutually_exclusive_group()
    upgrade_options.add_argument("--upgrade-evidence", default=None)
    upgrade_options.add_argument(
        "--no-upgrade-evidence", action="store_true",
        help="legacy/test-only opt-out from required upgrade evidence",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "freeze":
            freeze(args.assets, args.out)
        else:
            verify(
                args.candidate, args.evidence, args.upgrade_evidence,
                no_upgrade_evidence=args.no_upgrade_evidence,
            )
    except (Hold, OSError, ValueError, subprocess.SubprocessError) as exc:
        reason = " ".join(str(exc).split())
        print(f"HOLD: {reason}")
        return 1
    print("PASS: candidate frozen" if args.command == "freeze" else "PASS: candidate evidence verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
