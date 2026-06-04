"""memory_compactor.py — Compact Claude Code auto-memory at session end.

Actions:
1. Prune dead links from MEMORY.md (entries pointing to deleted files)
2. Archive stale project memories (older than MAX_AGE_DAYS)
3. Warn if MEMORY.md approaching 200-line limit
Called by ctx_end.py.
"""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

MAX_AGE_DAYS = 7
WARN_LINES = 150
MAX_LINES = 200


def _find_memory_dir(base: Path) -> Path | None:
    projects_dir = base / "_sys" / "claude" / "config" / "projects"
    if not projects_dir.exists():
        return None
    for project_dir in sorted(projects_dir.iterdir()):
        memory_dir = project_dir / "memory"
        if memory_dir.is_dir() and (memory_dir / "MEMORY.md").exists():
            return memory_dir
    return None


def _extract_file_ref(line: str) -> str | None:
    m = re.search(r'\[.*?\]\((.+?\.md)\)', line)
    return m.group(1) if m else None


def _memory_age_days(f: Path) -> int:
    return (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).days


def _memory_type(f: Path) -> str:
    try:
        content = f.read_text(encoding="utf-8")
        m = re.search(r'type:\s*(\w+)', content)
        return m.group(1) if m else "unknown"
    except Exception:
        return "unknown"


def compact(memory_dir: Path, archive_dir: Path, max_age_days: int = MAX_AGE_DAYS) -> dict:
    mem_file = memory_dir / "MEMORY.md"
    if not mem_file.exists():
        return {"status": "no_file", "lines": 0, "pruned": [], "archived": []}

    lines = mem_file.read_text(encoding="utf-8").splitlines()
    kept, pruned, archived = [], [], []

    for line in lines:
        ref = _extract_file_ref(line)
        if not ref:
            kept.append(line)
            continue

        target = memory_dir / ref
        if not target.exists():
            pruned.append(ref)
            continue

        # Feedback memories never expire; project memories expire after max_age_days
        if _memory_type(target) == "project" and _memory_age_days(target) > max_age_days:
            archive_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), archive_dir / target.name)
            archived.append(ref)
        else:
            kept.append(line)

    mem_file.write_text("\n".join(kept) + "\n", encoding="utf-8")
    n = len(kept)
    status = "over_limit" if n >= MAX_LINES else ("warning" if n >= WARN_LINES else "ok")
    return {"status": status, "lines": n, "pruned": pruned, "archived": archived}


def main(base_dir: Path | None = None) -> None:
    if base_dir is None:
        base_dir = Path.cwd()
        while not (base_dir / "_sys").exists():
            p = base_dir.parent
            if p == base_dir:
                print("[memory-compact] ERROR: project root not found.")
                return
            base_dir = p

    memory_dir = _find_memory_dir(base_dir)
    if not memory_dir:
        return

    archive_dir = base_dir / "_archive" / "memory"
    r = compact(memory_dir, archive_dir)

    if r["pruned"]:
        print(f"[memory-compact] Dead links pruned: {r['pruned']}")
    if r["archived"]:
        print(f"[memory-compact] Stale project memories archived: {r['archived']}")

    n = r["lines"]
    if r["status"] == "over_limit":
        print(f"[memory-compact] WARNING: MEMORY.md {n}/{MAX_LINES} lines — manual pruning needed.")
    elif r["status"] == "warning":
        print(f"[memory-compact] MEMORY.md {n}/{MAX_LINES} lines (nearing limit).")
    else:
        print(f"[memory-compact] MEMORY.md {n} lines — OK.")


if __name__ == "__main__":
    main()
