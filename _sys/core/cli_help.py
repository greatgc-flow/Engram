"""cli_help.py - single source of truth for `engram <verb> --help` and CLI usage errors.

Help text lives in static files, one per verb: ``core/help/<verb>.txt`` (plus ``index.txt`` for `engram help`).
engram.cmd prints them with ``type`` (works before Python is installed); Python verbs print the very same
files, so both paths always agree. Every verb file uses ONE layout:

    <title line>
    Usage: / Description: / Options: / Examples: / Exit codes: / See also:

This module only uses the standard library so it can also run standalone:

    python cli_help.py suggest-verb      # reads ENGRAM_UNKNOWN_VERB (and optionally ENGRAM_SUGGEST_FROM,
                                         # a comma list) and prints a "Did you mean ..." line
"""
from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
from pathlib import Path
from typing import Iterable, Optional

HELP_DIR = Path(__file__).resolve().parent / "help"
HELP_FLAGS = ("-h", "--help", "/?")
SECTIONS = ("Usage:", "Description:", "Options:", "Examples:", "Exit codes:", "See also:")
_FLAG_RE = re.compile(r"--?[A-Za-z][\w-]*")


def verbs() -> list[str]:
    """Public verbs = every help/<verb>.txt except the index."""
    if not HELP_DIR.is_dir():
        return []
    return sorted(p.stem for p in HELP_DIR.glob("*.txt") if p.stem != "index")


def help_text(verb: str) -> Optional[str]:
    """The verb's help text, or None when the verb is unknown (also for path-like names)."""
    if not re.fullmatch(r"[A-Za-z][\w-]*", verb or ""):
        return None
    path = HELP_DIR / f"{verb.lower()}.txt"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def print_verb_help(verb: str) -> None:
    text = help_text(verb)
    if text is None:
        text = f"engram {verb}: no help available.\n"
    sys.stdout.write(text if text.endswith("\n") else text + "\n")


def wants_help(args: Iterable[str]) -> bool:
    """True for -h/--help// ? anywhere, or the word 'help' as the first argument."""
    args = list(args)
    return any(a in HELP_FLAGS for a in args) or bool(args and args[0].lower() == "help")


def section(verb: str, name: str) -> list[str]:
    """Lines of one help section (heading line excluded); empty when absent."""
    text = help_text(verb)
    if text is None:
        return []
    lines, out, inside = text.split("\n"), [], False
    for line in lines:
        if line.startswith(name):
            inside = True
            rest = line[len(name):].strip()
            if rest:
                out.append(rest)
            continue
        if inside:
            if line and not line.startswith((" ", "\t")):
                break
            out.append(line)
    return out


def option_names(verb: str) -> set[str]:
    """Every flag named in the verb's Options section (the flag column only, not descriptions)."""
    found: set[str] = set()
    for line in section(verb, "Options:"):
        if not line.startswith("  ") or line.startswith("   "):
            continue
        column = re.split(r"\s{2,}", line.strip(), maxsplit=1)[0]
        found.update(_FLAG_RE.findall(column))
    return found


def suggest(word: str, candidates: Iterable[str], limit: int = 2, cutoff: float = 0.7) -> list[str]:
    """Near matches, best first; weaker ones only when they are almost as good as the best."""
    word = word.lower()
    pool = sorted(set(candidates))
    ranked = sorted(((difflib.SequenceMatcher(None, word, c.lower()).ratio(), c) for c in pool), reverse=True)
    ranked = [(r, c) for r, c in ranked if r >= cutoff]
    if not ranked:
        return []
    best = ranked[0][0]
    return [c for r, c in ranked if r >= best - 0.08][:limit]


def report_unknown(verb: str, kind: str, word: str, candidates: Iterable[str], message: Optional[str] = None) -> None:
    """Print the standard 'unknown <kind>' error with a 'Did you mean' line (does not exit)."""
    print(message or f"[Error] Unknown {kind} '{word}' for 'engram {verb}'.")
    hits = suggest(word, candidates)
    if hits:
        print("        Did you mean " + " or ".join(f"'{h}'" for h in hits) + "?")
    print(f"Run 'engram {verb} --help' for usage.")


def usage_error(verb: str, message: str, bad: Optional[str] = None) -> "None":
    """Print a consistent error (+ 'Did you mean') and exit 2. Never returns."""
    print(f"[Error] {message}")
    if bad and bad.startswith("-"):
        hits = suggest(bad.split("=", 1)[0], option_names(verb))
        if hits:
            print("        Did you mean " + " or ".join(f"'{h}'" for h in hits) + "?")
    print(f"Run 'engram {verb} --help' for usage.")
    raise SystemExit(2)


def unknown_option(verb: str, bad: str) -> "None":
    usage_error(verb, f"Unknown option '{bad}' for 'engram {verb}'.", bad)


def unexpected_argument(verb: str, bad: str) -> "None":
    usage_error(verb, f"Unexpected argument '{bad}' for 'engram {verb}'.")


class CliParser(argparse.ArgumentParser):
    """argparse with the engram help layout and consistent errors (exit 2, no traceback)."""

    def __init__(self, verb: str, **kwargs):
        kwargs.setdefault("prog", f"engram {verb}")
        kwargs["add_help"] = False
        super().__init__(**kwargs)
        self.verb = verb

    def print_help(self, file=None) -> None:  # noqa: D102
        print_verb_help(self.verb)

    def error(self, message: str):  # noqa: D102
        bad = None
        m = re.search(r"unrecognized arguments: (\S+)", message)
        if m:
            bad = m.group(1)
        else:
            m = re.search(r"ambiguous option: (\S+)", message)
            if m:
                bad = m.group(1)
        if bad and bad.startswith("-"):
            unknown_option(self.verb, bad)
        if bad:
            unexpected_argument(self.verb, bad)
        usage_error(self.verb, f"{message} (engram {self.verb})")

    def parse_args(self, args=None, namespace=None):  # noqa: D102
        args = list(sys.argv[1:] if args is None else args)
        if wants_help(args):
            self.print_help()
            raise SystemExit(0)
        ns, extra = self.parse_known_args(args, namespace)
        if extra:
            self.error("unrecognized arguments: " + " ".join(extra))
        return ns


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["suggest-verb"]:
        word = os.environ.get("ENGRAM_UNKNOWN_VERB", "")
        pool = [c for c in os.environ.get("ENGRAM_SUGGEST_FROM", "").split(",") if c] or verbs() + ["help"]
        hits = suggest(word, pool) if word else []
        if hits:
            print("Did you mean " + " or ".join(f"'{h}'" for h in hits) + "?")
        return 0
    print("usage: cli_help.py suggest-verb", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
