"""Verify the frozen design against Git objects, even on CRLF checkouts."""

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
from pathlib import Path

COMMIT = "c59c0e42bb6584bc873269b7128a1c94ecba3229"
PACKAGE = "docs/design/local-ai-pre-tdd/rev06"
ROOT = Path(__file__).resolve().parents[2]
FILES = {
    "README.md", "SPECIFICATION.md", "CONTRACTS.md", "DECISIONS.md",
    "REQUIREMENTS.csv", "TEST_CATALOG.csv", "IMPLEMENTATION_PLAN.md", "SOURCES.md",
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ids(prefix, size, width=2):
    return [f"{prefix}{n:0{width}}" for n in range(1, size + 1)]


def audit(ancestor=None):
    def blob(name):
        return git("show", f"{COMMIT}:{PACKAGE}/{name}")

    manifest = blob("MANIFEST.sha256").decode().splitlines()
    entries = [line.split("  ") for line in manifest]
    require(len(entries) == len(FILES) and {name for _, name in entries} == FILES, "manifest inventory")
    tree = git("ls-tree", "--name-only", f"{COMMIT}:{PACKAGE}").decode().splitlines()
    require(set(tree) == FILES | {"MANIFEST.sha256"}, "package inventory")
    for expected, name in entries:
        require(hashlib.sha256(blob(name)).hexdigest() == expected, name)
        require(git("show", f"HEAD:{PACKAGE}/{name}") == blob(name), f"HEAD drift: {name}")
    require(git("rev-parse", f"{COMMIT}:{PACKAGE}") == git("rev-parse", f"HEAD:{PACKAGE}"), "HEAD tree drift")

    def table(name):
        return list(csv.DictReader(io.StringIO(blob(name).decode())))

    cases, requirements = table("TEST_CATALOG.csv"), table("REQUIREMENTS.csv")
    require([c["test_id"] for c in cases] == ids("T", 150), "case IDs/order")
    require([r["requirement_id"] for r in requirements] == ids("R", 9), "requirement IDs/order")
    require(all(c["status"] == "NOT_RUN" for c in cases), "historical case states")
    links = [(i, r["requirement_id"]) for r in requirements for i in r["test_ids"].split(";")]
    require(sorted(links) == sorted((c["test_id"], c["requirement_id"]) for c in cases), "primary traceability")
    decisions = blob("DECISIONS.md").decode()
    for prefix, size in (("ADR-", 50), ("K", 28)):
        require(re.findall(r"^\| (" + prefix + r"\d+) \|", decisions, re.M) == ids(prefix, size), prefix)
    plan = blob("IMPLEMENTATION_PLAN.md").decode()
    require(re.findall(r"^\| (POC-\d+) \|", plan, re.M) == ids("POC-", 10), "POC IDs")
    require(re.findall(r"^\| (G\d) ", plan, re.M) == [f"G{i}" for i in range(8)], "gate IDs")
    if ancestor:
        raw = ancestor.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == "cece4b86ca4f5a1d096c97b1c0e556cecbc134763740a50cbad2b47b0ab45c01", "Rev05 identity")
        for prefix, size in (("ADR-", 30), ("T", 86)):
            require(re.findall(r"^\| (" + prefix + r"\d+) \|", raw.decode(), re.M) == ids(prefix, size), "ancestor IDs")
    return dict(commit=COMMIT, manifest_entries=8, cases=len(cases), requirement_groups=9,
                adrs=50, risks=28, spikes=10, gates=8, ancestor_ids="PASS" if ancestor else "NOT_RUN")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ancestor", type=Path, help="Optional original Rev05 document, read locally only")
    print(json.dumps(audit(parser.parse_args().ancestor), indent=2))
