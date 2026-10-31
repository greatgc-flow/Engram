"""Read-only audit of installed Engram tool provenance records.

Does not install, download, execute tools, or attest current executable bytes.
Exit codes: 0 recorded provenance matches; 2 HOLD; 1 input/evidence I/O error.
Only --evidence writes a file, with bytes identical to console JSON output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


PINNED_TOOLS = (
    "ripgrep", "bat", "fd", "delta", "fzf", "jq", "gh", "oh-my-posh"
)
DEFAULTS = Path(__file__).resolve().parents[1] / "defaults" / "runtimes.json"


def _read_dict(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("configuration/manifest must be a JSON object")
    return data


def _source_hash(cfg: dict[str, Any]) -> str:
    """Match provisioner._canon_hash without importing mutable runtime paths."""
    payload = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hold(reason: str) -> dict[str, str]:
    return {"status": "HOLD", "reason": reason}


def audit(sys_dir: Path, default_path: Path = DEFAULTS) -> dict[str, Any]:
    """Inspect active effective config, pinned defaults and recorded manifests.

    PASS_RECORDED does NOT mean files were independently hashed or reinstalled.
    """
    defaults = _read_dict(default_path).get("tools", {})
    effective_path = sys_dir / "runtimes.json"
    if not effective_path.exists():
        effective_path = sys_dir / "defaults" / "runtimes.json"
    actual = _read_dict(effective_path).get("tools", {}) if effective_path.exists() else {}
    if not isinstance(defaults, dict) or not isinstance(actual, dict):
        raise ValueError("runtimes.json tools must be an object")

    results: dict[str, dict[str, str]] = {}
    for name in PINNED_TOOLS:
        expected = defaults.get(name)
        cfg = actual.get(name)
        folder = sys_dir / "tools" / name
        manifest_path = folder / ".install_manifest.json"
        if not isinstance(expected, dict) or not isinstance(cfg, dict):
            results[name] = _hold("missing pinned default or effective tool declaration")
            continue
        if (
            not isinstance(expected.get("sha256"), str)
            or len(expected["sha256"]) != 64
        ):
            results[name] = _hold("invalid pinned SHA-256 default")
            continue
        if cfg != expected:
            results[name] = _hold("effective configuration differs from pinned default")
            continue
        if folder.is_symlink() or manifest_path.is_symlink():
            results[name] = _hold("symbolic-link installation path requires review")
            continue
        if not manifest_path.is_file():
            results[name] = _hold("installed manifest missing")
            continue
        try:
            manifest = _read_dict(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError):
            results[name] = _hold("installed manifest unreadable")
            continue

        if (
            manifest.get("declared_version") != cfg.get("version")
            or manifest.get("url") != cfg.get("url")
            or manifest.get("checksum_algo") != "sha256"
            or manifest.get("checksum_value") != cfg.get("sha256")
            or manifest.get("checksum_source") != "declared"
            or manifest.get("checksum_verified") is not True
            or manifest.get("source_config_hash") != _source_hash(cfg)
        ):
            results[name] = _hold("recorded provenance does not match pinned config")
            continue
        bin_name = cfg.get("bin")
        if not isinstance(bin_name, str) or not bin_name or Path(bin_name).name != bin_name:
            results[name] = _hold("invalid executable declaration")
            continue
        binary = folder / bin_name
        if binary.is_symlink() or not binary.is_file():
            results[name] = _hold("installed executable absent or symbolic link")
            continue
        required = cfg.get("required_paths") or []
        if not isinstance(required, list) or any(
            not isinstance(p, str) or not p or ".." in Path(p).parts
            or not (folder / p).is_dir() for p in required
        ):
            results[name] = _hold("required companion directories missing")
            continue
        results[name] = {
            "status": "PASS_RECORDED",
            "reason": "manifest matches pinned source; binary exists; bytes NOT independently verified",
        }

    failures = sum(r["status"] != "PASS_RECORDED" for r in results.values())
    return {
        "schema_version": 1,
        "overall": "PASS_RECORDED" if failures == 0 else "HOLD",
        "recorded_pass": len(results) - failures,
        "holds": failures,
        "items": results,
        "scope": "read-only manifest/source/physical-presence audit; not executable byte attestation",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sys-dir", required=True, type=Path,
                        help="Engram installed _sys directory, never modified")
    parser.add_argument("--evidence", type=Path,
                        help="Optional local evidence JSON; exact console bytes")
    args = parser.parse_args(argv)
    try:
        result = audit(args.sys_dir)
        output = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.evidence is not None:
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_bytes(output.encode("utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: installed provenance audit could not run: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(output)
    return 0 if result["overall"] == "PASS_RECORDED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
