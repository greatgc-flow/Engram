"""_common.py — Shared utilities for _sys/checks/ scripts."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

_CHECKS_DIR = Path(__file__).parent
_SYS_DIR = _CHECKS_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent



def build_env() -> dict:
    """Return subprocess env with PYTHONUTF8=1 and npm-global prepended to PATH."""
    e = {**os.environ, "PYTHONUTF8": "1"}
    npm_global = _SYS_DIR / "env" / "nodejs" / "npm-global"
    if npm_global.exists():
        e["PATH"] = str(npm_global) + ";" + e.get("PATH", "")
    return e


class ContractViolationError(ValueError):
    """Raised when an AI-produced JSON object violates a check output contract."""


class UnmergedIndexError(RuntimeError):
    """Raised when an unmerged git index entry is encountered."""
    pass


class IndexView:
    """View over the staged git index (git ls-files --stage -z)."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self._staged_map: dict[str, str] = {}  # rel_path -> oid
        self._text_cache: dict[str, str] = {}
        self._load_stage()

    def _load_stage(self) -> None:
        try:
            res = subprocess.run(
                ["git", "ls-files", "--stage", "-z"],
                capture_output=True,
                cwd=str(self.root),
                check=True,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise RuntimeError(f"Git index read failed: {exc}") from exc

        raw = res.stdout.decode("utf-8", errors="replace")
        entries = [e for e in raw.split("\0") if e]
        for entry in entries:
            try:
                meta, path_str = entry.split("\t", 1)
                mode, oid, stage_str = meta.split(" ", 2)
                stage = int(stage_str)
            except ValueError:
                continue
            if stage != 0:
                raise UnmergedIndexError(f"Unmerged index entry for '{path_str}' at stage {stage}")
            rel_path = path_str.replace("\\", "/").lstrip("/")
            self._staged_map[rel_path] = oid

    def list_files(self, prefix: str = "", suffix: str = "") -> list[str]:
        prefix_clean = prefix.replace("\\", "/").lstrip("/")
        suffix_clean = suffix.lower()
        res = []
        for path in self._staged_map.keys():
            if prefix_clean and not path.startswith(prefix_clean):
                continue
            if suffix_clean and not path.lower().endswith(suffix_clean):
                continue
            res.append(path)
        return sorted(res)

    def exists(self, rel_path: str) -> bool:
        clean = rel_path.replace("\\", "/").lstrip("/")
        return clean in self._staged_map

    def read_text(self, rel_path: str) -> str:
        clean = rel_path.replace("\\", "/").lstrip("/")
        if clean not in self._text_cache:
            self.read_many_text([clean])
        return self._text_cache[clean]

    def read_many_text(self, rel_paths: list[str]) -> dict[str, str]:
        """Batch-load staged blobs and cache their decoded text."""
        clean_paths = [
            path.replace("\\", "/").lstrip("/")
            for path in rel_paths
        ]
        missing = [
            path
            for path in dict.fromkeys(clean_paths)
            if path not in self._text_cache
        ]
        for path in missing:
            if path not in self._staged_map:
                raise FileNotFoundError(
                    f"File '{path}' not found in staged index"
                )
        if not missing:
            return {
                path: self._text_cache[path]
                for path in clean_paths
            }

        request = "".join(
            f"{self._staged_map[path]}\n"
            for path in missing
        ).encode("ascii")
        try:
            res = subprocess.run(
                ["git", "cat-file", "--batch"],
                input=request,
                capture_output=True,
                cwd=str(self.root),
                check=True,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise RuntimeError(
                f"Failed to batch-read {len(missing)} staged object(s): {exc}"
            ) from exc

        payload = res.stdout
        offset = 0
        for path in missing:
            newline = payload.find(b"\n", offset)
            if newline < 0:
                raise RuntimeError(
                    f"Malformed git cat-file header for '{path}'"
                )
            header = payload[offset:newline].decode(
                "ascii",
                errors="replace",
            )
            parts = header.split()
            if len(parts) != 3 or parts[1] != "blob":
                raise RuntimeError(
                    f"Unexpected git cat-file header for '{path}': {header}"
                )
            try:
                size = int(parts[2])
            except ValueError as exc:
                raise RuntimeError(
                    f"Invalid staged blob size for '{path}': {header}"
                ) from exc
            start = newline + 1
            end = start + size
            if end > len(payload):
                raise RuntimeError(
                    f"Truncated staged blob for '{path}'"
                )
            self._text_cache[path] = payload[start:end].decode(
                "utf-8",
                errors="replace",
            )
            offset = end + 1

        return {
            path: self._text_cache[path]
            for path in clean_paths
        }


class WorktreeView:
    """View over the filesystem worktree."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def list_files(self, prefix: str = "", suffix: str = "") -> list[str]:
        base_dir = (self.root / prefix) if prefix else self.root
        if not base_dir.exists():
            return []
        suffix_clean = suffix.lower()
        res = []
        for p in base_dir.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(self.root)).replace("\\", "/")
                if suffix_clean and not rel.lower().endswith(suffix_clean):
                    continue
                res.append(rel)
        return sorted(res)

    def exists(self, rel_path: str) -> bool:
        clean = rel_path.replace("\\", "/").lstrip("/")
        return (self.root / clean).exists()

    def read_text(self, rel_path: str) -> str:
        clean = rel_path.replace("\\", "/").lstrip("/")
        p = self.root / clean
        if not p.exists():
            raise FileNotFoundError(f"File '{rel_path}' not found in worktree")
        return p.read_text(encoding="utf-8", errors="replace")

