"""Capability resolver and check module (T43).
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CHECKS_DIR = Path(__file__).resolve().parent
_SYS_DIR = _CHECKS_DIR.parent
_PORTABLE_ROOT = _SYS_DIR.parent

if str(_SYS_DIR / "core") not in sys.path:
    sys.path.insert(0, str(_SYS_DIR / "core"))
if str(_CHECKS_DIR) not in sys.path:
    sys.path.insert(0, str(_CHECKS_DIR))

import check_peer_capability_canary
from snapshot import collect_snapshot


def values_equal(v1: Any, v2: Any) -> bool:
    """Compare point or range values for equality."""
    def get_numeric(v: Any) -> Any:
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, dict):
            if v.get("kind") == "point":
                return v.get("value")
            if v.get("kind") == "range":
                return (v.get("min"), v.get("max"))
        return None

    n1 = get_numeric(v1)
    n2 = get_numeric(v2)
    if n1 is None or n2 is None:
        return False
    if isinstance(n1, tuple) and isinstance(n2, tuple):
        return abs(n1[0] - n2[0]) < 1e-5 and abs(n1[1] - n2[1]) < 1e-5
    if isinstance(n1, (int, float)) and isinstance(n2, (int, float)):
        return abs(n1 - n2) < 1e-5
    return False


def validate_declarations(declarations: dict[str, Any], orch: dict[str, Any] | None = None) -> None:
    """Validate capability-declarations.json structure according to T43 rules."""
    if not isinstance(declarations, dict):
        raise ValueError("declarations must be a dictionary")
    
    schema_version = declarations.get("schema_version")
    if schema_version != 1:
        raise ValueError(f"unknown declarations schema_version: {schema_version}")

    valid_profiles = set()
    if orch and orch.get("hub_nodes"):
        for node in orch.get("hub_nodes", []):
            if node.get("type") == "peer":
                peer_id = node.get("node_id")
                for prof_name in node.get("profiles", {}).keys():
                    valid_profiles.add(f"{peer_id}.{prof_name}")

    subjects = declarations.get("subjects", {})
    if not isinstance(subjects, dict):
        raise ValueError("subjects must be a dictionary")

    for subject_id, subject_info in subjects.items():
        if not isinstance(subject_info, dict):
            raise ValueError(f"subject {subject_id} must be a dictionary")
        
        subj = subject_info.get("subject", {})
        peer = subj.get("peer")
        profile = subj.get("profile")
        deployed_model_id = subj.get("deployed_model_id")
        reasoning_effort = subj.get("reasoning_effort")
        adapter = subj.get("adapter")

        if not all(isinstance(x, str) and x.strip() for x in (peer, profile, deployed_model_id, reasoning_effort, adapter)):
            raise ValueError(f"malformed subject info for {subject_id}")

        if valid_profiles and f"{peer}.{profile}" not in valid_profiles:
            raise ValueError(f"unknown subject-profile: {peer}.{profile}")

        axes = subject_info.get("axes", {})
        if not isinstance(axes, dict):
            raise ValueError(f"axes for {subject_id} must be a dictionary")

        for axis_name, axis_info in axes.items():
            if not isinstance(axis_info, dict):
                raise ValueError(f"axis {axis_name} under {subject_id} must be a dictionary")
            
            # 1. Missing fields check
            required_keys = {"scale", "source_kind", "verification", "source_ref", "as_of"}
            missing = required_keys - set(axis_info.keys())
            if missing:
                raise ValueError(f"missing {list(missing)} in axis {axis_name} of {subject_id}")

            # 2. Illegal combos check
            source_kind = axis_info.get("source_kind")
            verification = axis_info.get("verification")
            
            legal = False
            if source_kind == "declared" and verification == "unverified":
                legal = True
            elif source_kind == "empirical_probe" and verification == "machine_observed":
                legal = True
            elif source_kind in ("app_server", "statusline", "cli_live") and verification == "machine_observed":
                legal = True
            elif source_kind == "absent" and verification == "absent":
                legal = True

            if not legal:
                raise ValueError(f"illegal source_kind ({source_kind}) x verification ({verification}) combo in {subject_id}/{axis_name}")


def get_operational_value(row: dict[str, Any], axis: str) -> dict[str, Any] | None:
    """Retrieve operational data from a snapshot profile row for a given axis."""
    if axis in ("context_window", "window_tokens", "long_context_quality"):
        ctx = row.get("context", {})
        tag = ctx.get("source_tag")
        if tag in ("app_server", "statusline", "cli_live"):
            val = ctx.get("window_tokens")
            if val is not None:
                return {
                    "value": val,
                    "source_tag": tag,
                    "verification": "machine_observed"
                }
    return None


def resolve_capability_reality(
    orch: dict[str, Any],
    snapshot: dict[str, Any],
    declarations: dict[str, Any],
    score_entries: list[dict[str, Any]],
    now: datetime
) -> dict[str, Any]:
    """Resolve the capability reality overlay per subject/axis (T43 resolver)."""
    # Validate declarations structure first
    validate_declarations(declarations, orch)

    # An empirical record without a valid T41 fingerprint is UNTRUSTED EVIDENCE —
    # filter it out of resolution rather than raising (T52 C2: a single
    # fingerprint-less record, e.g. a long_context.* record, would otherwise
    # ValueError the ENTIRE overlay). check_reality_rules still flags it; resolve
    # must degrade gracefully. Records missing a numeric single-axis `score`
    # (e.g. multi-axis capability-core.v1 records that carry only axis_scores) are
    # likewise not single-axis evidence and are skipped -> ABSENT, not a
    # CERTIFIED-but-None band (T52 C1). Full per-axis integration is a follow-up.
    score_entries = [
        e for e in score_entries
        if not (
            e.get("source_tag") == "empirical_probe"
            and (
                not check_peer_capability_canary.runtime_fingerprint_valid(e.get("runtime_fingerprint"))
                or not isinstance(e.get("score"), (int, float))
            )
        )
    ]

    subjects = set(declarations.get("subjects", {}).keys())
    for entry in score_entries:
        if entry.get("peer") and entry.get("profile"):
            subjects.add(f"{entry['peer']}.{entry['profile']}")
    for r in snapshot.get("profiles", []):
        if r.get("profile"):
            subjects.add(r["profile"])

    resolved_subjects = {}

    for subject in subjects:
        peer, _, profile = subject.partition(".")
        decl_info = declarations.get("subjects", {}).get(subject)
        
        axes = set()
        if decl_info:
            axes.update(decl_info.get("axes", {}).keys())
        
        # Add axes from score entries
        for entry in score_entries:
            if (entry.get("peer") == peer and
                entry.get("profile") == profile and
                entry.get("capability_id")):
                axes.add(entry["capability_id"])
        
        # If we have operational snapshot row, maybe it adds operational axes
        row = None
        for r in snapshot.get("profiles", []):
            if r.get("profile") == subject:
                row = r
                break
        
        if row:
            # If snapshot profile row has operational context telemetry, add context_window axis
            ctx_tag = row.get("context", {}).get("source_tag")
            if ctx_tag in ("app_server", "statusline", "cli_live"):
                axes.add("context_window")

        resolved_axes = {}
        expected_fp = check_peer_capability_canary.resolve_runtime_fingerprint(orch, peer, profile)

        for axis in axes:
            # Filter score entries for this subject and axis
            entries = [
                e for e in score_entries
                if (e.get("peer") == peer and
                    e.get("profile") == profile and
                    e.get("capability_id") == axis)
            ]

            # Matching fingerprint entries
            matching_entries = [
                e for e in entries
                if check_peer_capability_canary._same_runtime(e.get("runtime_fingerprint"), expected_fp)
            ]
            matching_entries.sort(key=lambda e: check_peer_capability_canary._parse_iso(e.get("measured_at")) or datetime.min.replace(tzinfo=timezone.utc))

            # Mismatched/expired/failed entries
            mismatched_entries = [
                e for e in entries
                if not check_peer_capability_canary._same_runtime(e.get("runtime_fingerprint"), expected_fp)
            ]

            failed_entries = []
            expired_entries = []
            valid_empirical = None

            if matching_entries:
                latest_entry = matching_entries[-1]
                if latest_entry.get("passed") is False:
                    failed_entries.append(latest_entry)
                else:
                    # Check expiry
                    expires_at = check_peer_capability_canary._parse_iso(latest_entry.get("expires_at"))
                    if expires_at and expires_at <= now:
                        expired_entries.append(latest_entry)
                    else:
                        valid_empirical = latest_entry

            stale_evidence = mismatched_entries + expired_entries + failed_entries
            stale_evidence.sort(key=lambda e: check_peer_capability_canary._parse_iso(e.get("measured_at")) or datetime.min.replace(tzinfo=timezone.utc))

            # Precedence Resolution
            effective_value = None
            scale = None
            source_tag = "absent"
            verification = "absent"
            evidence_band = "ABSENT"

            decl_axis = decl_info.get("axes", {}).get(axis) if decl_info else None
            if decl_axis:
                scale = decl_axis.get("scale")

            # 1. Valid empirical probe
            if valid_empirical:
                effective_value = valid_empirical.get("score")
                scale = "local_suite"
                source_tag = "empirical_probe"
                verification = "machine_observed"
                evidence_band = "CERTIFIED"

            # 2. Operational data
            elif row and get_operational_value(row, axis):
                op_val = get_operational_value(row, axis)
                if op_val:
                    effective_value = op_val["value"]
                    scale = "context_tokens"
                    source_tag = op_val["source_tag"]
                    verification = op_val["verification"]
                    evidence_band = "EXPLORATORY"

            # 3. Declared fallback
            elif decl_axis:
                # Gated check: a declaration with NO empirical entry resolves ABSENT
                if not entries:
                    evidence_band = "ABSENT"
                else:
                    effective_value = decl_axis.get("value")
                    scale = decl_axis.get("scale")
                    source_tag = "declared"
                    verification = "unverified"
                    evidence_band = "DECLARED"
            
            # 4. Stale (expired empirical with no declaration)
            elif entries:
                evidence_band = "STALE"

            # Compute reconcile_status
            reconcile_status = "ABSENT"
            
            # Contradicted check: has past pass but latest matching failed
            has_past_pass = any(e.get("passed") is True for e in matching_entries[:-1])
            if matching_entries and matching_entries[-1].get("passed") is False and has_past_pass:
                reconcile_status = "CONTRADICTED"
            
            # Reconcile MATCH/DRIFT within the same scale
            elif effective_value is not None:
                if decl_axis and decl_axis.get("scale") == scale:
                    decl_val = decl_axis.get("value")
                    if values_equal(effective_value, decl_val):
                        reconcile_status = "MATCH"
                    else:
                        reconcile_status = "DRIFT"

            resolved_axes[axis] = {
                "effective_value": effective_value,
                "scale": scale,
                "source_tag": source_tag,
                "verification": verification,
                "evidence_band": evidence_band,
                "reconcile_status": reconcile_status,
                "stale_evidence": stale_evidence
            }

        resolved_subjects[subject] = {
            "subject": decl_info.get("subject") if decl_info else {
                "peer": peer,
                "profile": profile,
                "deployed_model_id": row.get("model") if row else "Unknown",
                "reasoning_effort": row.get("effort") if row else "Unknown",
                "adapter": "Unknown"
            },
            # T45 consumes this declared operational feasibility annotation
            # only to distinguish measurable profiles from PTY-blocked ones;
            # it is not capability evidence and never supplies a score.
            "measurement_feasibility": (decl_info or {}).get("measurement_feasibility"),
            "axes": resolved_axes
        }

    return {
        "schema_version": 1,
        "subjects": resolved_subjects
    }


def check_reality_rules(reality: dict[str, Any]) -> list[str]:
    """Validate check rules on the resolved reality object."""
    errors = []
    for subject_id, subj_info in reality.get("subjects", {}).items():
        for axis_name, axis_info in subj_info.get("axes", {}).items():
            evidence_band = axis_info.get("evidence_band")
            reconcile_status = axis_info.get("reconcile_status")
            source_tag = axis_info.get("source_tag")
            verification = axis_info.get("verification")
            scale = axis_info.get("scale")
            
            # 1. Missing scale | source_kind | verification.
            # ABSENT and STALE carry no effective value (STALE = an expired/failed
            # empirical with no declaration fallback), so scale is legitimately
            # unset for them; only value-bearing bands must be fully qualified.
            if evidence_band not in ("ABSENT", "STALE") and not all((scale, source_tag, verification)):
                errors.append(f"{subject_id}/{axis_name}: missing scale|source_tag|verification")

            # 2. Illegal combos
            legal = False
            if source_tag == "declared" and verification == "unverified":
                legal = True
            elif source_tag == "empirical_probe" and verification == "machine_observed":
                legal = True
            elif source_tag in ("app_server", "statusline", "cli_live") and verification == "machine_observed":
                legal = True
            elif source_tag == "absent" and verification == "absent":
                legal = True

            if not legal:
                errors.append(f"{subject_id}/{axis_name}: illegal source_tag ({source_tag}) x verification ({verification}) combo")

            # 3. Expired empirical selected as effective (should be STALE/DECLARED fallback)
            if evidence_band == "CERTIFIED" and source_tag != "empirical_probe":
                errors.append(f"{subject_id}/{axis_name}: certified but source_tag is {source_tag}")

            # 4. DRIFT/CONTRADICTED
            if reconcile_status in ("DRIFT", "CONTRADICTED"):
                errors.append(f"{subject_id}/{axis_name}: reconcile status is {reconcile_status}")

    return errors


def main() -> int:
    """Run check_capability as a command line check."""
    now = datetime.now(timezone.utc)
    try:
        orch = check_peer_capability_canary._load_orchestration()
        snapshot = collect_snapshot()
        
        declarations_path = _SYS_DIR / "ai" / "capability-declarations.json"
        if not declarations_path.exists():
            print(f"Error: declarations file not found at {declarations_path}")
            return 1
        
        declarations = json.loads(declarations_path.read_text(encoding="utf-8"))
        score_entries = check_peer_capability_canary.load_score_entries()
        
        reality = resolve_capability_reality(orch, snapshot, declarations, score_entries, now)
        
        # Write reality to .ai/capability-reality.json
        reality_path = _PORTABLE_ROOT / ".ai" / "capability-reality.json"
        reality_path.parent.mkdir(parents=True, exist_ok=True)
        reality_path.write_text(json.dumps(reality, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Wrote reality overlay to {reality_path}")

        errors = check_reality_rules(reality)
        if errors:
            print("Capability check failed:")
            for err in errors:
                print(f"  - {err}")
            return 1
        
        print("Capability check passed.")
        return 0
    except Exception as exc:
        print(f"Error executing capability check: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
