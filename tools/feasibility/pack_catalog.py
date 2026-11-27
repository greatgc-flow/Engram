"""Inspect TEST_ONLY descriptors and synthetic slot paths without running package code."""
import argparse
import json
from pathlib import Path
import sys

SYSTEM = Path(__file__).resolve().parents[2] / "_sys"
sys.path.insert(0, str(SYSTEM))
from core.pack_catalog import MAX_BYTES, observe_slots, read_catalog  # noqa: E402

REVIEWED_SLOTS = {"ai": "AI", "contentflow": "ContentFlow"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("system_dir", type=Path)
    parser.add_argument("descriptors", type=Path, nargs="*")
    args = parser.parse_args()
    try:
        payloads = []
        for path in args.descriptors:
            with path.open("rb") as stream:
                payloads.append(stream.read(MAX_BYTES + 1))
        catalog = read_catalog(payloads, REVIEWED_SLOTS)
        print(json.dumps(observe_slots(args.system_dir, catalog), sort_keys=True))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Catalog inspection failed: {exc}\n")


if __name__ == "__main__":
    main()
