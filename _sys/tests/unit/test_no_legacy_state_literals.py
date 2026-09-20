import os
import re
from pathlib import Path
from _sys.core.root import find_root

def test_no_legacy_state_literals():
    root = find_root(__file__).parent

    # Regex to match path-segment literal .ai or _archive
    # (^|[\/"'])\.ai([\/"']|$)
    pattern = re.compile(r'(^|[\\/"\'])(?:\.ai|_archive)([\\/"\']|$)')

    failures = []

    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)

        # We should only scan the packaged files.
        parts = rel_dir.parts
        if parts and parts[0] == "_sys" and len(parts) >= 2 and parts[1] in ("tests", "docs", "data"):
            continue
        if parts and parts[0] in (".git", "workspace", ".engram", ".ai", "_archive", "dist", "manifests", "tools", ".pytest_cache"):
            continue

        for f in filenames:
            if not f.endswith((".py", ".bat", ".cmd", ".json", ".ps1")):
                continue

            filepath = Path(dirpath) / f
            try:
                content = filepath.read_text(encoding="utf-8")
                for i, line in enumerate(content.splitlines(), 1):
                    if "# legacy-source: migration only" in line:
                        continue
                    if pattern.search(line):
                        failures.append(f"{filepath.relative_to(root)}:{i}: {line.strip()}")
            except UnicodeDecodeError:
                pass

    if failures:
        msg = "\n".join(failures)
        assert False, f"Found legacy state literals (.ai or _archive) in packaged code:\n{msg}"
