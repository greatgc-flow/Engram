"""Inspect TEST_ONLY descriptors and synthetic slot paths without running package code."""
import argparse
import json
from pathlib import Path
import sys

SYSTEM = Path(__file__).resolve().parents[2] / "_sys"
sys.path.insert(0, str(SYSTEM))
from core import cli_help, provisioner  # noqa: E402
from optional_pack_catalog import MAX_BYTES, observe_slots, read_catalog  # noqa: E402

from optional_pack_registry import observe_registry  # noqa: E402

REVIEWED_SLOTS = {"ai": "AI", "contentflow": "ContentFlow"}


def load_fixtures(paths):
    payloads = []
    for path in paths:
        with path.open("rb") as stream:
            payloads.append(stream.read(MAX_BYTES + 1))
    commands = set(cli_help.verbs())
    catalog_path = provisioner.resolve_declared_config(SYSTEM, provisioner.TOOL_CATALOG_FILENAME)
    host_tools = json.loads(catalog_path.read_text(encoding="utf-8"))
    for tool in host_tools["tools"]:
        commands.add(tool["tool_id"])
        commands.update(tool["aliases"])
    return read_catalog(payloads, REVIEWED_SLOTS, commands)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("system_dir", type=Path)
    parser.add_argument("descriptors", type=Path, nargs="*")
    parser.add_argument("--installation-id", help="expected fixture owner for registry inspection")
    args = parser.parse_args()
    try:
        catalog = load_fixtures(args.descriptors)
        if args.installation_id is None:
            status = observe_slots(args.system_dir, catalog)
        else:
            status = observe_registry(args.system_dir, catalog, args.installation_id)
        print(json.dumps(status, sort_keys=True))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Catalog inspection failed: {exc}\n")


if __name__ == "__main__":
    main()
