#!/usr/bin/env python3
"""check_cli_canary.py — real-invocation canary check for peer CLIs.

Proves E2E execution of peer CLIs at a bounded, budgeted token cost.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Setup sys.path for _sys imports
_CHECKS_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CHECKS_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent
_AI_DIR = _PORTABLE_ROOT / ".ai"

if str(_SYS_DIR / "core") not in sys.path:
    sys.path.insert(0, str(_SYS_DIR / "core"))

if str(_CHECKS_DIR) not in sys.path:
    sys.path.insert(0, str(_CHECKS_DIR))

from hub_peer import normalize_orchestration, validate_model_operand, get_adapter
from _common import build_env
from check_cli_reality import fingerprint, real_binary


def _cheapest_profile(node: dict) -> str | None:
    """Return the name of the cheapest enabled profile of a peer.
    Tiers are ordered: 'low' < 'mid' < 'high'.
    Profiles with routing_state == 'blocked' are excluded.
    """
    tier_order = {"low": 0, "mid": 1, "high": 2}
    best_profile = None
    best_tier = float("inf")
    
    profiles = node.get("profiles", {})
    for p_name, p_config in profiles.items():
        if p_config.get("routing_state") == "blocked":
            continue
        tier = p_config.get("cost_tier", "high")
        tier_val = tier_order.get(tier, 2)
        if tier_val < best_tier:
            best_tier = tier_val
            best_profile = p_name
        elif tier_val == best_tier:
            if best_profile is None or p_name < best_profile:
                best_profile = p_name
    return best_profile


def get_cache_key(binary_fingerprint: str, invoke_args: list[str], model_id: str, prompt_version: str = "v1") -> str:
    """Return stable sha256 of parameters for caching."""
    invoke_args_str = json.dumps(invoke_args, sort_keys=True)
    payload = f"{binary_fingerprint}:{invoke_args_str}:{model_id}:{prompt_version}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_budget_config(orch: dict | None) -> tuple[int, float]:
    """Retrieve budget configuration (cap and window hours) from orchestration config."""
    if orch:
        cfg = orch.get("canary_config", {})
        cap = cfg.get("budget_cap", 10)
        window = cfg.get("budget_window_hours", 5.0)
        return int(cap), float(window)
    return 10, 5.0


def check_and_update_budget(ai_root: Path, now_ts: float, cap: int = 10, window_hours: float = 5.0) -> bool:
    """Return True if under budget, False otherwise."""
    budget_file = ai_root / "canary_budget.json"
    if not budget_file.exists():
        return True
    try:
        invocations = json.loads(budget_file.read_text(encoding="utf-8"))
    except Exception:
        invocations = []

    cutoff = now_ts - (window_hours * 3600)
    valid_invocations = [t for t in invocations if isinstance(t, (int, float)) and t >= cutoff]
    return len(valid_invocations) < cap


def record_budget_invocation(ai_root: Path, now_ts: float):
    """Record an invocation timestamp to budget file."""
    budget_file = ai_root / "canary_budget.json"
    invocations = []
    if budget_file.exists():
        try:
            invocations = json.loads(budget_file.read_text(encoding="utf-8"))
        except Exception:
            invocations = []
    invocations.append(now_ts)
    
    # Prune old invocations to keep file size small (keep past 24 hours)
    cutoff = now_ts - 24 * 3600
    invocations = [t for t in invocations if isinstance(t, (int, float)) and t >= cutoff]
    
    try:
        ai_root.mkdir(parents=True, exist_ok=True)
        budget_file.write_text(json.dumps(invocations), encoding="utf-8")
    except Exception:
        pass


def load_cache(ai_root: Path) -> dict:
    """Load the canary cache."""
    cache_file = ai_root / "canary_cache.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(ai_root: Path, cache: dict):
    """Save the canary cache."""
    cache_file = ai_root / "canary_cache.json"
    try:
        ai_root.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _default_invoker(orch: dict) -> Callable[[str, str, str, str], str]:
    """Build the real one-shot command and execute it via subprocess."""
    def invoker(peer: str, profile: str, model: str, prompt: str) -> str:
        # Find the profile node
        norm_orch = normalize_orchestration(orch)
        profile_node = None
        for node in norm_orch.get("hub_nodes", []):
            if node.get("node_id") == f"{peer}.{profile}" and node.get("type") == "profile":
                profile_node = node
                break

        if not profile_node:
            raise RuntimeError(f"Profile {peer}.{profile} not found")

        # Get adapter and build command
        adapter = get_adapter(profile_node)
        cmd, use_stdin = adapter.build_cmd(profile_node, prompt)

        # Resolve relative executable paths
        if cmd:
            executable = cmd[0]
            exec_path = Path(executable)
            if not exec_path.is_absolute() and exec_path.parts and exec_path.parts[0].casefold() == "_sys":
                cmd[0] = str((_SYS_DIR.parent / exec_path).resolve())

        # Execute
        stdin_data = prompt if use_stdin else None
        try:
            res = subprocess.run(
                cmd,
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=60,
                env=build_env(),
            )
        except Exception as exc:
            raise RuntimeError(f"Subprocess launch failed: {exc}")

        if res.returncode != 0:
            err_msg = res.stderr or res.stdout or f"exit code {res.returncode}"
            raise RuntimeError(f"Command failed with code {res.returncode}: {err_msg}")

        # Parse and strip logs
        parsed = adapter.parse_output(res.stdout, profile_node)
        lines = []
        for line in parsed.splitlines():
            # Strip common hub/logging prefixes
            if any(line.startswith(prefix) for prefix in ("[HUB]", "[collab_log]", "[INFO]", "[DEBUG]", "[WARN]")):
                continue
            lines.append(line)
        return "\n".join(lines).strip()

    return invoker


def canary_probe(
    peer: str,
    profile_name: str,
    orch: dict,
    invoker: Callable[[str, str, str, str], str] | None = None,
    now: datetime | None = None,
    force: bool = False,
    ai_root: Path | None = None,
    bypass_budget: bool = False,
) -> dict:
    """Run a single canary probe for a peer profile.

    `force` bypasses the result cache (re-invoke even on a cached PASS).
    `bypass_budget` bypasses the invocation-budget gate independently, for
    operator-intended runs (all-profiles / explicit peer or profile).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    ts_iso = now.isoformat()
    if ai_root is None:
        ai_root = _AI_DIR

    # 1. Resolve the node + profile from orch
    norm_orch = normalize_orchestration(orch)
    profile_node = None
    for node in norm_orch.get("hub_nodes", []):
        if node.get("node_id") == f"{peer}.{profile_name}" and node.get("type") == "profile":
            profile_node = node
            break

    if not profile_node:
        return {
            "peer": peer,
            "profile": profile_name,
            "status": "FAIL",
            "stage": "operand_validation",
            "detail": f"Profile node {peer}.{profile_name} not found in orchestration",
            "ts": ts_iso,
        }

    # 2. Build the model operand check
    err = validate_model_operand(profile_node)
    if err:
        return {
            "peer": peer,
            "profile": profile_name,
            "status": "FAIL",
            "stage": "operand_validation",
            "detail": err,
            "ts": ts_iso,
        }

    model_id = profile_node.get("model_id") or profile_node.get("runtime_model") or ""

    # 3. Retrieve fingerprint and build cache key
    fp_info = fingerprint(real_binary(peer))
    binary_fp = fp_info.get("sha256") or ""
    invoke_args = profile_node.get("invoke_args") or []
    # Identity-qualify the cache key so distinct (peer, profile) never collide even
    # when the binary fingerprint is shared/mocked.
    cache_key = get_cache_key(binary_fp, [f"{peer}.{profile_name}"] + list(invoke_args), model_id, "v1")

    # 4. Check cache if not force
    if not force:
        cache = load_cache(ai_root)
        if cache_key in cache:
            cached_verdict = cache[cache_key]
            if cached_verdict.get("status") == "PASS":
                res = dict(cached_verdict)
                res["cached"] = True
                return res

    # 5. Check budget before invoking. `force` bypasses only the cache; the
    # budget is bypassed independently via `bypass_budget` (operator-intended
    # all-profiles / explicit runs), so a forced single probe still counts.
    now_ts = now.timestamp()
    cap, window_hours = get_budget_config(orch)
    if not bypass_budget and not check_and_update_budget(ai_root, now_ts, cap, window_hours):
        return {
            "peer": peer,
            "profile": profile_name,
            "status": "SKIP",
            "reason": "budget",
            "ts": ts_iso,
        }

    # 6. Resolve invoker
    if invoker is None:
        invoker = _default_invoker(orch)

    # 7. Invoke
    prompt = "Respond with exactly: OK"
    record_budget_invocation(ai_root, now_ts)

    try:
        verdict_text = invoker(peer, profile_name, model_id, prompt)
    except Exception as exc:
        return {
            "peer": peer,
            "profile": profile_name,
            "status": "FAIL",
            "stage": "launch",
            "detail": str(exc)[:200],
            "ts": ts_iso,
        }

    # 8. Assertions from the reply. The prompt demands exactly "OK", so require
    # an exact normalized match — a substring test would false-PASS on replies
    # like "NOT OK" or "OK but failed".
    reply_stripped = verdict_text.strip()
    is_ok = reply_stripped.upper() == "OK"

    status = "PASS" if is_ok else "FAIL"
    stage = "reply"
    
    verdict = {
        "peer": peer,
        "profile": profile_name,
        "model": model_id,
        "status": status,
        "stage": stage,
        "reply": verdict_text[:80],
        "ts": ts_iso,
    }

    # 9. Record PASS in cache
    if status == "PASS":
        cache = load_cache(ai_root)
        cache[cache_key] = verdict
        save_cache(ai_root, cache)

    return verdict


def run_canary(
    orch: dict | None = None,
    peers: list[str] | None = None,
    all_profiles: bool = False,
    force: bool = False,
    invoker: Callable[[str, str, str, str], str] | None = None,
    ai_root: Path | None = None,
) -> list[dict]:
    """Run canary probes across target peers and profiles."""
    if orch is None:
        orch_path = _SYS_DIR / "ai" / "orchestration.json"
        try:
            orch = json.loads(orch_path.read_text(encoding="utf-8"))
        except Exception:
            orch = {}
            
    if ai_root is None:
        ai_root = _AI_DIR
        
    targets: list[tuple[str, str, bool]] = []
    nodes = {n["node_id"]: n for n in orch.get("hub_nodes", []) if n.get("node_id")}
    
    if peers is not None:
        for item in peers:
            if "." in item:
                peer_id, profile_name = item.split(".", 1)
                targets.append((peer_id, profile_name, True))
            else:
                peer_id = item
                node = nodes.get(peer_id)
                if not node or not node.get("enabled", True):
                    continue
                if all_profiles:
                    for p_name in (node.get("profiles") or {}):
                        targets.append((peer_id, p_name, True))
                else:
                    cheapest = _cheapest_profile(node)
                    if cheapest:
                        targets.append((peer_id, cheapest, False))
    else:
        for peer_id, node in nodes.items():
            if node.get("type") == "peer" and node.get("enabled", True):
                if all_profiles:
                    for p_name in (node.get("profiles") or {}):
                        targets.append((peer_id, p_name, True))
                else:
                    cheapest = _cheapest_profile(node)
                    if cheapest:
                        targets.append((peer_id, cheapest, False))
                        
    filtered_targets: list[tuple[str, str, bool]] = []
    for peer_id, p_name, is_explicit in targets:
        node = nodes.get(peer_id)
        if not node:
            continue
        p_config = node.get("profiles", {}).get(p_name)
        if not p_config:
            continue
        if p_config.get("routing_state") == "blocked":
            continue

        cost_tier = p_config.get("cost_tier", "high")
        is_premium = cost_tier == "high"

        if is_premium and not (all_profiles or is_explicit):
            continue

        filtered_targets.append((peer_id, p_name, is_explicit))

    verdicts = []
    for peer_id, p_name, is_explicit in filtered_targets:
        # An operator-intended run (all_profiles or an explicit peer/profile) is
        # not the automatic budget-gated path — bypass the budget (but keep the
        # cache unless the caller explicitly asked to --force a fresh probe).
        bypass_budget = all_profiles or is_explicit
        try:
            verdict = canary_probe(
                peer_id, p_name, orch, invoker=invoker,
                force=force, ai_root=ai_root, bypass_budget=bypass_budget,
            )
            verdicts.append(verdict)
        except Exception as exc:
            verdicts.append({
                "peer": peer_id,
                "profile": p_name,
                "status": "FAIL",
                "stage": "launch",
                "detail": f"Crash in run_canary: {exc}",
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            
    return verdicts


def print_verdicts_table(verdicts: list[dict]):
    """Print the list of verdicts in a clean aligned table format."""
    headers = ["PEER", "PROFILE", "MODEL", "STATUS", "STAGE", "REPLY/DETAIL"]
    rows = []
    for v in verdicts:
        peer = v.get("peer", "-")
        profile = v.get("profile", "-")
        model = v.get("model") or "-"
        status = v.get("status", "-")
        stage = v.get("stage") or v.get("reason") or "-"
        reply_or_detail = v.get("reply") or v.get("detail") or "-"
        if len(reply_or_detail) > 50:
            reply_or_detail = reply_or_detail[:47] + "..."
        rows.append([peer, profile, model, status, stage, reply_or_detail])
        
    widths = [len(h) for h in headers]
    for r in rows:
        for i, val in enumerate(r):
            widths[i] = max(widths[i], len(str(val)))
            
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print(fmt.format(*r))


def main(argv: list[str] | None = None) -> int:
    import argparse
    
    parser = argparse.ArgumentParser(description="check_cli_canary.py — real-invocation canary check for peer CLIs")
    parser.add_argument("--peer", help="Comma-separated list of peer IDs or peer.profile strings (e.g., cc,ag.deepthink)")
    parser.add_argument("--all-profiles", action="store_true", help="Probe all profiles for selected peers instead of cheapest")
    parser.add_argument("--force", action="store_true", help="Bypass cache and force invocation")
    args = parser.parse_args(argv)
    
    orch_path = _SYS_DIR / "ai" / "orchestration.json"
    try:
        orch = json.loads(orch_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Error loading orchestration.json: {exc}")
        return 1
        
    peers_list = None
    if args.peer:
        peers_list = [p.strip() for p in args.peer.split(",")]
        
    verdicts = run_canary(
        orch=orch,
        peers=peers_list,
        all_profiles=args.all_profiles,
        force=args.force,
        ai_root=_AI_DIR
    )
    
    if not verdicts:
        print("No active targets matched the request.")
        return 0
        
    print_verdicts_table(verdicts)
    
    has_fail = any(v.get("status") == "FAIL" for v in verdicts)
    return 1 if has_fail else 0


if __name__ == "__main__":
    sys.exit(main())
