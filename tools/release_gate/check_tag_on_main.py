"""Fail closed unless a release tag commit is an ancestor of origin/main.

The caller must fetch the tag and origin/main before running this gate.
"""

import argparse
import re
import subprocess


class Hold(ValueError):
    """The release tag cannot be promoted."""


def check_tag_on_main(tag, *, runner=None, ref="origin/main"):
    if (not isinstance(tag, str) or not tag or tag.startswith("-")
            or any(character.isspace() for character in tag)):
        raise Hold("missing or invalid release tag")
    if (not isinstance(ref, str) or not ref or ref.startswith("-")
            or any(character.isspace() for character in ref)):
        raise Hold("missing or invalid reference branch")
    runner = subprocess.run if runner is None else runner
    try:
        result = runner(
            ["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        commit = result.stdout.strip()
        if result.returncode != 0 or not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", commit):
            raise Hold("release tag commit is unavailable")
        result = runner(
            ["git", "merge-base", "--is-ancestor", commit, ref],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise Hold("release tag ancestry is unavailable") from exc
    if result.returncode != 0:
        raise Hold(f"release tag commit is not a verified ancestor of {ref}")


def main(argv=None, *, runner=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--ref", default="origin/main")
    args = parser.parse_args(argv)
    try:
        check_tag_on_main(args.tag, runner=runner, ref=args.ref)
    except Hold as exc:
        print(f"HOLD: {exc}")
        return 1
    print(f"PASS: release tag commit is an ancestor of {args.ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
