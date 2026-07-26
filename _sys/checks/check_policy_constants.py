"""check_policy_constants.py — no-hardcoding / policy-drift guard (CHK-CONST).

Enforces token-session-policy-design-2026-07-08 §2: operational policy constants
live in JSON config (telemetry-config.json / routing-config.json), not as raw
magic numbers scattered in code. Three checks, low false-positive:

  CHK-CONST-1: the telemetry constants in snapshot.py are assigned FROM
               telemetry_config() subscript chains (not hardcoded or reassigned).
  CHK-CONST-2: telemetry-config.json is schema-complete vs _TELEMETRY_DEFAULTS
               (every section/key present with the right type).
  CHK-CONST-3: routing-config.token_load_balancing carries the documented
               operational knobs (so a rename/removal is caught).

Usage:  python check_policy_constants.py [--json]
Exit:   0 clean · 1 at least one violation.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

_CHECKS_DIR = Path(__file__).parent
_SYS_DIR = _CHECKS_DIR.parent
_SNAPSHOT = _SYS_DIR / "core" / "snapshot.py"
_TELEMETRY_JSON = _SYS_DIR / "ai" / "telemetry-config.json"
_ROUTING_JSON = _SYS_DIR / "ai" / "routing-config.json"

_CONFIG_SOURCED = {
    "SNAPSHOT_TTL_SEC", "EXPENSIVE_SOURCE_TTL_SEC", "_LOCAL_TTL_SEC",
    "QUOTA_WARN_FRAC", "QUOTA_CRIT_FRAC", "CLI_REALITY_REFRESH_SLO_HOURS",
}

_TELEMETRY_SCHEMA = {
    "ttl": {"snapshot_sec": int, "expensive_source_sec": int, "local_sec": int},
    "probe": {"deadline_sec": int},
    "cli_reality": {"refresh_slo_hours": float},
    "display": {"warn_frac": float, "crit_frac": float},
    "watch": {"default_interval_sec": int, "min_interval_sec": int, "sync_output": str},
}

_ROUTING_REQUIRED_KNOBS = [
    "enabled", "effective_headroom_floor", "headroom_bias",
    "context_affinity", "bulk_exclude_profiles",
]


def _is_valid_telemetry_subscript(node: ast.AST) -> bool:
    """Returns True if node is a Subscript chain whose innermost value is telemetry_config()."""
    if not isinstance(node, ast.Subscript):
        return False
    curr = node
    while isinstance(curr, ast.Subscript):
        curr = curr.value
    return (
        isinstance(curr, ast.Call)
        and isinstance(curr.func, ast.Name)
        and curr.func.id == "telemetry_config"
        and not curr.args
        and not curr.keywords
    )


def _check_config_sourced() -> list[str]:
    """CHK-CONST-1: each named constant assigned from telemetry_config() subscript chain."""
    out: list[str] = []
    if not _SNAPSHOT.exists():
        return [f"CHK-CONST-1: snapshot.py not found at {_SNAPSHOT}"]

    try:
        src = _SNAPSHOT.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(_SNAPSHOT))
    except Exception as exc:
        return [f"CHK-CONST-1: failed to parse snapshot.py: {exc}"]

    assigned_names: dict[str, int] = {name: 0 for name in _CONFIG_SOURCED}

    # Only inspect top-level statements in snapshot.py (do not walk into functions/classes)
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                target_name = None
                if isinstance(target, ast.Name):
                    target_name = target.id
                elif isinstance(target, ast.Subscript):
                    # Catch globals()["NAME"] = ...
                    val = target.value
                    if (
                        isinstance(val, ast.Call)
                        and isinstance(val.func, ast.Name)
                        and val.func.id == "globals"
                        and isinstance(target.slice, ast.Constant)
                        and isinstance(target.slice.value, str)
                    ):
                        target_name = target.slice.value

                if target_name and target_name in _CONFIG_SOURCED:
                    assigned_names[target_name] += 1
                    if assigned_names[target_name] > 1:
                        out.append(
                            f"CHK-CONST-1: {target_name} is reassigned multiple times at module level"
                        )
                    if not _is_valid_telemetry_subscript(stmt.value):
                        out.append(
                            f"CHK-CONST-1: {target_name} is hardcoded or not loaded from a valid "
                            "telemetry_config() subscript chain"
                        )

        elif isinstance(stmt, ast.AugAssign):
            target = stmt.target
            target_name = target.id if isinstance(target, ast.Name) else None
            if target_name and target_name in _CONFIG_SOURCED:
                out.append(f"CHK-CONST-1: {target_name} uses illegal AugAssign (reassignment)")

    for name, count in assigned_names.items():
        if count == 0:
            out.append(f"CHK-CONST-1: {name} not found in snapshot.py module-level statements")

    return out


def _check_telemetry_schema() -> list[str]:
    """CHK-CONST-2: telemetry-config.json complete + correctly typed."""
    out: list[str] = []
    try:
        cfg = json.loads(_TELEMETRY_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"CHK-CONST-2: telemetry-config.json unreadable ({exc})"]
    for section, keys in _TELEMETRY_SCHEMA.items():
        got = cfg.get(section)
        if not isinstance(got, dict):
            out.append(f"CHK-CONST-2: missing section '{section}'")
            continue
        for key, typ in keys.items():
            if key not in got:
                out.append(f"CHK-CONST-2: missing '{section}.{key}'")
            elif not isinstance(got[key], typ) or isinstance(got[key], bool) and typ is not bool:
                out.append(f"CHK-CONST-2: '{section}.{key}' wrong type "
                           f"(want {typ.__name__}, got {type(got[key]).__name__})")
    return out


def _check_routing_knobs() -> list[str]:
    """CHK-CONST-3: routing-config token_load_balancing keeps documented knobs."""
    try:
        rc = json.loads(_ROUTING_JSON.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"CHK-CONST-3: routing-config.json unreadable ({exc})"]
    tlb = rc.get("token_load_balancing", {}) or {}
    return [f"CHK-CONST-3: token_load_balancing missing knob '{k}'"
            for k in _ROUTING_REQUIRED_KNOBS if k not in tlb]


def run() -> list[str]:
    return _check_config_sourced() + _check_telemetry_schema() + _check_routing_knobs()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="policy-constant / no-hardcoding guard")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    violations = run()
    if args.json:
        print(json.dumps({"check": "CHK-CONST", "ok": not violations,
                          "violations": violations}, ensure_ascii=False, indent=2))
    elif violations:
        print("[CHK-CONST] Policy-constant violations:")
        for v in violations:
            print(f"  - {v}")
        print("[CHK-CONST] Fix: move the value into telemetry-config.json / "
              "routing-config.json and load it via config (design 2026-07-08 §2).")
    else:
        print("[CHK-CONST] OK — policy constants are config-sourced.")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
