"""check_encoding.py — UTF-8 / mojibake guard for governed text (CHK-ENC).

Catches the class of corruption seen in the 2026-07-07 incident, where a
low-tier terminal re-saved docs and destroyed every non-ASCII character
(— § • → ×) into a literal ASCII '?' (0x3F). Strict-UTF-8 validation alone
does NOT catch that (an ASCII '?' is valid UTF-8), so this guard also runs a
git-diff *regression* heuristic: if a tracked file loses non-ASCII characters
while gaining '?' characters, that is the mojibake signature.

Two independent checks per file:
  1. STRICT-UTF-8 : bytes must decode as strict UTF-8 and contain no U+FFFD
     replacement characters (catches cp1252/UTF-16 lossy re-saves that emit ).
  2. MOJIBAKE-REGRESSION : vs the HEAD blob, flag when non-ASCII count drops
     while '?' count rises past a threshold (catches the → '?' class).

Usage:
    python check_encoding.py                 # staged files (pre-commit)
    python check_encoding.py --all           # whole working tree
    python check_encoding.py --json          # machine-readable result

Exit codes:
    0 — clean
    1 — at least one violation
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

_CHECKS_DIR = Path(__file__).parent
_SYS_DIR = _CHECKS_DIR.parent
_ROOT = _SYS_DIR.parent
_GOVERNANCE_PATH = _SYS_DIR / "ai" / "governance_params.json"

# Governed text globs (repo-relative, forward slashes). Extend via governance.
_DEFAULT_GOVERNED = [
    "_sys/docs-v2/**/*.md",
    "_sys/**/*.md",
    "*.md",
    "_sys/ai/**/*.json",
    "_sys/**/*.txt",
]

# Never scanned: archives / history / scratch / build junk. Extend via governance.
_DEFAULT_EXEMPT = [
    "_archive/",
    "_sys/docs/history/",
    "Garbage/",
    "scratch/",
    "__pycache__/",
    ".git/",
    "node_modules/",
]

# Regression thresholds: how much non-ASCII loss + '?' gain counts as mojibake.
_NONASCII_DROP_MIN = 2
_QMARK_GAIN_MIN = 2


def _load_governance() -> dict:
    if _GOVERNANCE_PATH.exists():
        try:
            return json.loads(_GOVERNANCE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _config() -> tuple[list[str], list[str]]:
    gov = _load_governance()
    governed = gov.get("encoding_guard_governed_globs", _DEFAULT_GOVERNED)
    exempt = gov.get("encoding_guard_exempt_paths", _DEFAULT_EXEMPT)
    return governed, exempt


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(_ROOT),
        capture_output=True, text=False,
    )


def _staged_paths() -> list[str]:
    cp = _git("diff", "--cached", "--name-only", "--diff-filter=ACM")
    if cp.returncode != 0:
        return []
    out = cp.stdout.decode("utf-8", "replace")
    return [line.strip() for line in out.splitlines() if line.strip()]


def _worktree_paths() -> list[str]:
    cp = _git("ls-files")
    if cp.returncode != 0:
        return []
    out = cp.stdout.decode("utf-8", "replace")
    return [line.strip() for line in out.splitlines() if line.strip()]


def _is_governed(path: str, governed: list[str], exempt: list[str]) -> bool:
    norm = path.replace("\\", "/")
    if any(ex.rstrip("/") + "/" in norm + "/" or norm.startswith(ex) for ex in exempt):
        return False
    return any(fnmatch.fnmatch(norm, g) for g in governed)


def _staged_bytes(path: str) -> bytes | None:
    cp = _git("show", f":{path}")
    return cp.stdout if cp.returncode == 0 else None


def _head_bytes(path: str) -> bytes | None:
    cp = _git("show", f"HEAD:{path}")
    return cp.stdout if cp.returncode == 0 else None


def _worktree_bytes(path: str) -> bytes | None:
    fp = _ROOT / path
    try:
        return fp.read_bytes()
    except OSError:
        return None


def _nonascii_and_qmark(text: str) -> tuple[int, int]:
    nonascii = sum(1 for ch in text if ord(ch) > 127)
    qmark = text.count("?")
    return nonascii, qmark


def _check_one(path: str, new_bytes: bytes, base_bytes: bytes | None) -> list[str]:
    """Return list of violation messages for one file."""
    violations: list[str] = []

    # Check 1: strict UTF-8 + no U+FFFD replacement char.
    try:
        text = new_bytes.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        violations.append(f"{path}: not valid UTF-8 ({exc.reason} at byte {exc.start})")
        return violations
    if "�" in text:
        n = text.count("�")
        violations.append(f"{path}: contains {n} U+FFFD replacement char(s) — lossy re-save")

    # Check 2: mojibake regression vs base (HEAD). New files skip this.
    if base_bytes is not None:
        try:
            base_text = base_bytes.decode("utf-8", "strict")
        except UnicodeDecodeError:
            return violations
        base_na, base_q = _nonascii_and_qmark(base_text)
        new_na, new_q = _nonascii_and_qmark(text)
        drop = base_na - new_na
        gain = new_q - base_q
        if base_na > 0 and drop >= _NONASCII_DROP_MIN and gain >= _QMARK_GAIN_MIN:
            violations.append(
                f"{path}: mojibake regression — non-ASCII {base_na}->{new_na} "
                f"(-{drop}) while '?' {base_q}->{new_q} (+{gain}); "
                f"unicode likely destroyed into '?'"
            )
    return violations


def run(scan_all: bool) -> list[str]:
    governed, exempt = _config()
    paths = _worktree_paths() if scan_all else _staged_paths()
    paths = [p for p in paths if _is_governed(p, governed, exempt)]

    all_violations: list[str] = []
    for path in paths:
        if scan_all:
            new_bytes = _worktree_bytes(path)
            base_bytes = _head_bytes(path)
        else:
            new_bytes = _staged_bytes(path)
            base_bytes = _head_bytes(path)
        if new_bytes is None:
            continue
        all_violations.extend(_check_one(path, new_bytes, base_bytes))
    return all_violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="UTF-8 / mojibake guard (CHK-ENC)")
    ap.add_argument("--all", action="store_true",
                    help="scan whole working tree (default: staged files only)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    violations = run(args.all)

    if args.json:
        print(json.dumps({
            "check": "CHK-ENC",
            "ok": not violations,
            "violations": violations,
        }, ensure_ascii=False, indent=2))
    else:
        if violations:
            print("[CHK-ENC] Encoding / mojibake violations:")
            for v in violations:
                print(f"  - {v}")
            print("[CHK-ENC] Fix: re-save the file as UTF-8 (no BOM). "
                  "A terminal writing files MUST use encoding-safe tooling.")
        else:
            print("[CHK-ENC] OK — no encoding/mojibake issues.")

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
