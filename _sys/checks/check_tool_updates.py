"""Measured tool update discovery for _sys/runtimes.json.

This check is read-only with respect to the real runtimes.json. With
--propose-diff it writes proposal artifacts under _archive/tool-updates/.
"""
from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CHECKS_DIR = Path(__file__).parent
_SYS_DIR = _CHECKS_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

sys.path.insert(0, str(_SYS_DIR / "core"))
import version_resolver  # noqa: E402

RUNTIMES_PATH = _SYS_DIR / "runtimes.json"
ARCHIVE_ROOT = _PORTABLE_ROOT / "_archive" / "tool-updates"
DISCOVERY_CACHE_PATH = _PORTABLE_ROOT / ".ai" / "tool_discovery_cache.json"
RETENTION_KEEP = 20


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(_PORTABLE_ROOT))
    except ValueError:
        return str(path)


def _versions_equal(a: str, b: str) -> bool:
    def norm(v: str) -> str:
        v = str(v).strip()
        return v[1:] if v.startswith("v") and len(v) > 1 else v
    return norm(a) == norm(b)


def _iter_discoverable_entries(runtimes: dict[str, Any]):
    for section in ("tools", "runtimes"):
        entries = runtimes.get(section, {})
        if not isinstance(entries, dict):
            continue
        for name, cfg in entries.items():
            if not isinstance(cfg, dict):
                continue
            provider = cfg.get("discovery_provider")
            if not provider or provider == "manual":
                continue
            discovery_id = cfg.get("discovery_id")
            if not discovery_id:
                yield section, name, cfg, None, "missing discovery_id"
                continue
            yield section, name, cfg, str(provider), None


def _update_entry_from_discovery(entry: dict[str, Any], discovery: dict[str, Any]) -> None:
    latest = discovery.get("latest_version")
    if latest:
        entry["version"] = latest
    if discovery.get("url"):
        entry["url"] = discovery["url"]

    algo = discovery.get("checksum_algo")
    value = discovery.get("checksum_value")
    if algo and value and algo in {"sha256", "sha512", "sha3_256"}:
        entry[algo] = value


def discover_updates() -> tuple[dict[str, Any], dict[str, Any], str]:
    base_sha = _sha256_file(RUNTIMES_PATH)
    runtimes = _read_json(RUNTIMES_PATH)
    proposed = copy.deepcopy(runtimes)

    payload: dict[str, Any] = {
        "artifact_dir": None,
        "base_sha256": base_sha,
        "updates_discovered": [],
        "up_to_date": [],
        "rate_limited": [],
        "errors": [],
    }

    for section, name, cfg, provider, config_error in _iter_discoverable_entries(runtimes):
        if config_error:
            payload["errors"].append({"tool": name, "error": config_error})
            continue

        current_version = str(cfg.get("version", ""))
        discovery = version_resolver.resolve_latest(
            tool_name=name,
            provider=str(provider),
            current_version=current_version,
            discovery_id=str(cfg.get("discovery_id")),
            cache_path=DISCOVERY_CACHE_PATH,
        )

        status = discovery.get("status")
        if status == "discovery_unavailable":
            payload["rate_limited"].append(name)
            continue
        if status != "ok":
            payload["errors"].append({
                "tool": name,
                "status": status,
                "error_type": discovery.get("error_type"),
                "detail": discovery.get("detail"),
            })
            continue

        latest_version = str(discovery.get("latest_version", ""))
        if not latest_version:
            payload["errors"].append({"tool": name, "error": "discovery result missing latest_version"})
            continue

        if _versions_equal(current_version, latest_version):
            payload["up_to_date"].append(name)
            continue

        update = {
            "tool": name,
            "current_version": current_version,
            "latest_version": latest_version,
            "url": discovery.get("url"),
            "checksum_algo": discovery.get("checksum_algo"),
            "checksum_value": discovery.get("checksum_value"),
        }
        payload["updates_discovered"].append(update)
        _update_entry_from_discovery(proposed[section][name], discovery)

    return payload, runtimes, proposed


def prune_tool_update_archives(archive_root: Path = ARCHIVE_ROOT, keep: int = RETENTION_KEEP) -> None:
    if keep < 1 or not archive_root.exists():
        return
    dirs = [p for p in archive_root.iterdir() if p.is_dir()]
    dirs.sort(key=lambda p: p.name, reverse=True)
    for old in dirs[keep:]:
        shutil.rmtree(old, ignore_errors=True)


def write_proposal_artifacts(payload: dict[str, Any], runtimes: dict[str, Any], proposed: dict[str, Any]) -> Path:
    artifact_dir = ARCHIVE_ROOT / _utc_stamp()
    suffix = 1
    while artifact_dir.exists():
        artifact_dir = ARCHIVE_ROOT / f"{_utc_stamp()}-{suffix}"
        suffix += 1
    artifact_dir.mkdir(parents=True, exist_ok=False)

    payload["artifact_dir"] = _display_path(artifact_dir)
    proposal_path = artifact_dir / "proposal.json"
    proposed_path = artifact_dir / "runtimes.proposed.json"
    diff_path = artifact_dir / "runtimes.diff"

    _write_json(proposal_path, payload)
    _write_json(proposed_path, proposed)

    current_text = json.dumps(runtimes, ensure_ascii=False, indent=4).splitlines(keepends=True)
    proposed_text = json.dumps(proposed, ensure_ascii=False, indent=4).splitlines(keepends=True)
    diff = difflib.unified_diff(
        current_text,
        proposed_text,
        fromfile=str(RUNTIMES_PATH),
        tofile=str(proposed_path),
    )
    diff_path.write_text("".join(diff), encoding="utf-8")

    prune_tool_update_archives()
    return artifact_dir


def verify_proposal_still_valid(artifact_dir: str | Path) -> bool:
    proposal_path = Path(artifact_dir) / "proposal.json"
    try:
        proposal = _read_json(proposal_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    expected = proposal.get("base_sha256")
    if not isinstance(expected, str) or not expected:
        return False
    try:
        current = _sha256_file(RUNTIMES_PATH)
    except OSError:
        return False
    return current == expected


def run(*, propose_diff: bool = False) -> dict[str, Any]:
    payload, runtimes, proposed = discover_updates()
    if propose_diff:
        write_proposal_artifacts(payload, runtimes, proposed)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measured update discovery for _sys/runtimes.json")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--propose-diff", action="store_true", help="write read-only proposal artifacts")
    args = parser.parse_args(argv)

    try:
        payload = run(propose_diff=args.propose_diff)
    except Exception as exc:
        payload = {
            "artifact_dir": None,
            "base_sha256": None,
            "updates_discovered": [],
            "up_to_date": [],
            "rate_limited": [],
            "errors": [{"error": str(exc)}],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    if args.json or args.propose_diff:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"[tool-updates] updates: {len(payload['updates_discovered'])}")
        print(f"[tool-updates] up-to-date: {len(payload['up_to_date'])}")
        print(f"[tool-updates] rate-limited: {len(payload['rate_limited'])}")
        print(f"[tool-updates] errors: {len(payload['errors'])}")

    return 1 if payload["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
