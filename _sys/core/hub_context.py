"""
hub_context.py — ContextGate v2.0 & C3 Prune-Path Fix: token estimation and context capacity resolution.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import unicodedata
from pathlib import Path
from typing import Any

try:
    from .hub_peer import canonical_reality_model_key
except ImportError:
    from hub_peer import canonical_reality_model_key

_CORE_DIR = Path(__file__).parent
_SYS_DIR = _CORE_DIR.parent
_AI_DIR = _SYS_DIR / "ai"
_GOVERNANCE_PATH = _AI_DIR / "governance_params.json"
_MODEL_REGISTRY_PATH = _AI_DIR / "model-registry.json"


@dataclass(frozen=True)
class ResolvedContextTarget:
    """C2/C3: Resolved context capacity target contract."""
    profile_id: str
    admission_limit: int
    limit_basis: str  # "profile_declared_limit" | "registry_model_id" | "exact_registry_model_id"
    registry_model_id: str | None
    context_window_kind: str  # "ceiling" | "proven_lower_bound"


@dataclass(frozen=True)
class ResolvedDispatchTarget:
    """C2+C11 composition without conflating capacity and CLI identities."""
    profile_id: str
    context_target: ResolvedContextTarget
    reality_model_key: str


@dataclass(frozen=True)
class ContextFailoverPlan:
    """C3: Immutable context failover plan contract produced by Hub capacity planner."""
    source_profile: str
    target_profile: str
    source_utilization: float
    target_utilization: float
    admission_limit: int
    limit_basis: str
    context_window_kind: str
    prune_applied: bool
    session_policy: str  # Always "fresh" for auto failover
    reason: str


def _cjk_ratio(text: str) -> float:
    """Return fraction of characters that are CJK (or Hangul)."""
    if not text:
        return 0.0
    cjk = sum(
        1 for ch in text
        if unicodedata.category(ch) in ("Lo", "Lm") and ord(ch) > 0x1000
    )
    return cjk / len(text)


def estimate_tokens(text: str) -> int:
    """Estimate token count. CJK text uses 1.8x multiplier (chars/3.5 * 1.8 per lifecycle.md:379)."""
    if not text:
        return 0
    ratio = _cjk_ratio(text)
    if ratio >= 0.20:
        return int(len(text) / 3.5 * 1.8)
    return int(len(text) / 3.5)


class ContextGateError(RuntimeError):
    """Raised when context cannot be reduced or context limit is exceeded."""
    def __init__(self, estimated_tokens: int, context_limit: int, model_id: str, utilization: float | None = None) -> None:
        util_val = utilization if isinstance(utilization, (int, float)) else (estimated_tokens / context_limit if context_limit else 0.0)
        super().__init__(
            f"CONTEXT_GATE_REJECT: {estimated_tokens} estimated tokens ({util_val:.1%}) exceeds "
            f"{int(context_limit * 0.95):.0f} failover threshold "
            f"for model {model_id} (limit={context_limit})"
        )
        self.estimated_tokens = estimated_tokens
        self.context_limit = context_limit
        self.model_id = model_id
        self.utilization = util_val
        self.error_type = "CONTEXT_GATE_REJECT"
        self.tier = "T2"


class UnknownModelCapacityError(ContextGateError):
    """C2 Priority 4: Raised when a profile or model's context capacity cannot be resolved."""
    def __init__(self, target_id: str, details: str = "") -> None:
        msg = f"UNKNOWN_MODEL_CAPACITY: Cannot resolve context limit for target '{target_id}'"
        if details:
            msg += f" ({details})"
        super().__init__(0, 0, target_id, utilization=None)
        self.args = (msg,)
        self.target_id = target_id
        self.details = details
        self.error_type = "UNKNOWN_MODEL_CAPACITY"

    def __str__(self) -> str:
        return self.args[0]


class ContextGateConfigError(ContextGateError):
    """C2: Raised when model-registry.json or governance config has invalid schema/data."""
    def __init__(self, config_path: Path, details: str) -> None:
        msg = f"CONTEXT_GATE_CONFIG_ERROR: Invalid config at {config_path}: {details}"
        super().__init__(0, 0, "config", utilization=None)
        self.args = (msg,)
        self.config_path = config_path
        self.details = details
        self.error_type = "CONTEXT_GATE_CONFIG_ERROR"

    def __str__(self) -> str:
        return self.args[0]


def _load_strict_json(path: Path, *, validate_registry: bool = False) -> dict:
    """Load JSON with strict schema validation. Raises ContextGateConfigError on corruption or schema mismatch."""
    if not path.exists():
        if validate_registry:
            raise ContextGateConfigError(path, "File does not exist")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ContextGateConfigError(path, f"JSON parse error: {exc}") from exc

    if not isinstance(data, dict):
        raise ContextGateConfigError(path, "Root JSON value must be an object (dict)")

    if validate_registry:
        models = data.get("models")
        if not isinstance(models, dict):
            raise ContextGateConfigError(path, "Registry 'models' key must be an object (dict)")
        for mid, mcfg in models.items():
            if not isinstance(mcfg, dict):
                raise ContextGateConfigError(path, f"Model entry '{mid}' must be an object (dict)")
            if "context_limit" in mcfg:
                clim = mcfg["context_limit"]
                if not isinstance(clim, int) or isinstance(clim, bool) or clim <= 0:
                    raise ContextGateConfigError(path, f"Model '{mid}' has non-positive or non-integer context_limit={clim!r}")

    return data


def resolve_context_target(
    target: str | dict[str, Any] | ResolvedContextTarget,
    registry_path: Path | None = None,
    orchestration_path: Path | None = None,
    *,
    registry_data: dict[str, Any] | None = None,
    profiles_data: dict[str, Any] | None = None,
) -> ResolvedContextTarget:
    """C2: Strict priority resolution of a profile or model target to a ResolvedContextTarget."""
    if isinstance(target, ResolvedContextTarget):
        return target

    reg_path = registry_path or _MODEL_REGISTRY_PATH
    reg = registry_data if isinstance(registry_data, dict) else _load_strict_json(reg_path, validate_registry=True)
    models_dict = reg.get("models", {})

    if not isinstance(target, str) or not target.strip():
        raise UnknownModelCapacityError(str(target), "Empty or invalid target specifier")

    target_id = target.strip()

    if profiles_data is None:
        try:
            from hub import _load_model_profiles
            profiles_catalog = _load_model_profiles().get("profiles", {})
        except Exception:
            profiles_catalog = {}
    else:
        profiles_catalog = profiles_data.get("profiles", profiles_data) if isinstance(profiles_data, dict) else {}

    pdata = profiles_catalog.get(target_id, {}) if isinstance(profiles_catalog, dict) else {}

    # Priority 1: runtime_context_window
    rcw = pdata.get("runtime_context_window")
    if isinstance(rcw, int) and not isinstance(rcw, bool) and rcw > 0:
        kind = "proven_lower_bound" if (
            target_id == "ag.gptoss"
            or pdata.get("context_window_kind") == "proven_lower_bound"
            or pdata.get("validation_method") == "sentinel_bound_probe_lower_bound"
        ) else "ceiling"
        reg_model_id = pdata.get("registry_model_id") or pdata.get("model_id")
        return ResolvedContextTarget(
            profile_id=target_id,
            admission_limit=rcw,
            limit_basis="profile_declared_limit",
            registry_model_id=str(reg_model_id) if reg_model_id else None,
            context_window_kind=kind,
        )

    # Priority 2: registry_model_id in pdata
    reg_model_id = pdata.get("registry_model_id")
    if isinstance(reg_model_id, str) and reg_model_id:
        if reg_model_id in models_dict:
            m_cfg = models_dict[reg_model_id]
            if isinstance(m_cfg, dict):
                clim = m_cfg.get("context_limit")
                if isinstance(clim, int) and not isinstance(clim, bool) and clim > 0:
                    kind = "proven_lower_bound" if (
                        target_id == "ag.gptoss"
                        or pdata.get("context_window_kind") == "proven_lower_bound"
                    ) else "ceiling"
                    return ResolvedContextTarget(
                        profile_id=target_id,
                        admission_limit=clim,
                        limit_basis="registry_model_id",
                        registry_model_id=reg_model_id,
                        context_window_kind=kind,
                    )

    # Priority 3: model_id in pdata & exact registry key match
    mid = pdata.get("model_id")
    if isinstance(mid, str) and mid:
        if mid in models_dict:
            m_cfg = models_dict[mid]
            if isinstance(m_cfg, dict):
                clim = m_cfg.get("context_limit")
                if isinstance(clim, int) and not isinstance(clim, bool) and clim > 0:
                    kind = "proven_lower_bound" if (
                        target_id == "ag.gptoss"
                        or pdata.get("context_window_kind") == "proven_lower_bound"
                    ) else "ceiling"
                    return ResolvedContextTarget(
                        profile_id=target_id,
                        admission_limit=clim,
                        limit_basis="exact_registry_model_id",
                        registry_model_id=mid,
                        context_window_kind=kind,
                    )

    # Check if target_id itself is a direct key in models_dict
    if target_id in models_dict:
        m_cfg = models_dict[target_id]
        if isinstance(m_cfg, dict):
            clim = m_cfg.get("context_limit")
            if isinstance(clim, int) and not isinstance(clim, bool) and clim > 0:
                return ResolvedContextTarget(
                    profile_id=target_id,
                    admission_limit=clim,
                    limit_basis="exact_registry_model_id",
                    registry_model_id=target_id,
                    context_window_kind="ceiling",
                )

    # Priority 4: fail closed
    raise UnknownModelCapacityError(
        target_id,
        f"Target '{target_id}' has no valid runtime_context_window and no matching registry entry with a positive context_limit"
    )


def resolve_dispatch_target(
    target: str | ResolvedDispatchTarget,
    registry_path: Path | None = None,
    *,
    registry_data: dict[str, Any] | None = None,
    profiles_data: dict[str, Any] | None = None,
) -> ResolvedDispatchTarget:
    """Compose C2 context capacity with C11's peer-CLI model identity.

    ``context_target`` answers how much context the selected profile can
    admit. ``reality_model_key`` is independently derived from the actual
    model operand sent to that peer CLI.  Keeping them side by side prevents
    registry aliases/capacity IDs from being mistaken for operational model
    evidence.
    """
    if isinstance(target, ResolvedDispatchTarget):
        return target
    if not isinstance(target, str) or not target.strip():
        raise UnknownModelCapacityError(str(target), "Empty or invalid dispatch target")

    profile_id = target.strip()
    context_target = resolve_context_target(
        profile_id,
        registry_path=registry_path,
        registry_data=registry_data,
        profiles_data=profiles_data,
    )

    if profiles_data is None:
        try:
            from hub import _load_model_profiles
            profiles_catalog = _load_model_profiles().get("profiles", {})
        except Exception:
            profiles_catalog = {}
    else:
        profiles_catalog = (
            profiles_data.get("profiles", profiles_data)
            if isinstance(profiles_data, dict)
            else {}
        )

    pdata = profiles_catalog.get(profile_id, {}) if isinstance(profiles_catalog, dict) else {}
    raw_model_key = pdata.get("model_id") or pdata.get("runtime_model")
    if not raw_model_key:
        args = list(pdata.get("profile_args") or [])
        for index, arg in enumerate(args):
            text = str(arg)
            if text in {"--model", "-m"} and index + 1 < len(args):
                raw_model_key = args[index + 1]
                break
            if text.startswith("--model="):
                raw_model_key = text.split("=", 1)[1]
                break

    # A direct registry/model target has no profile metadata. It is still a
    # valid reality operand in its own peer namespace when the caller supplies
    # such a target explicitly.
    raw_model_key = raw_model_key or context_target.registry_model_id or profile_id
    return ResolvedDispatchTarget(
        profile_id=profile_id,
        context_target=context_target,
        reality_model_key=canonical_reality_model_key(raw_model_key),
    )


class ContextGate:
    """Config-driven context gate. Estimates token usage and decides action."""

    def __init__(
        self,
        governance_path: Path | None = None,
        registry_path: Path | None = None,
    ) -> None:
        self._gov_path = governance_path or _GOVERNANCE_PATH
        self._reg_path = registry_path or _MODEL_REGISTRY_PATH
        self._gov = _load_strict_json(self._gov_path, validate_registry=False)
        self._registry = _load_strict_json(self._reg_path, validate_registry=True)

    def resolve_target(self, target: str | dict[str, Any] | ResolvedContextTarget) -> ResolvedContextTarget:
        """Resolve a target specifier to a ResolvedContextTarget contract."""
        return resolve_context_target(
            target,
            registry_path=self._reg_path,
            registry_data=self._registry,
        )

    def resolve_dispatch_target(
        self,
        target: str | ResolvedDispatchTarget,
    ) -> ResolvedDispatchTarget:
        return resolve_dispatch_target(
            target,
            registry_path=self._reg_path,
            registry_data=self._registry,
        )

    @property
    def enabled(self) -> bool:
        return bool(self._gov.get("context_gate_enabled", True))

    @property
    def warn_pct(self) -> float:
        return float(self._gov.get("context_gate_warn_pct", 0.80))

    @property
    def failover_pct(self) -> float:
        return float(self._gov.get("context_gate_failover_pct", 0.95))

    def context_limit(self, target: str | dict[str, Any] | ResolvedContextTarget) -> int:
        """Return resolved admission limit for target. Raises UnknownModelCapacityError on miss."""
        resolved = self.resolve_target(target)
        return resolved.admission_limit

    def check(self, text: str, target: str | dict[str, Any] | ResolvedContextTarget) -> dict[str, Any]:
        """Evaluate text length against resolved model context limit."""
        resolved = self.resolve_target(target)
        estimated = estimate_tokens(text)
        limit = resolved.admission_limit
        warn_t = int(limit * self.warn_pct)
        failover_t = int(limit * self.failover_pct)
        utilization = estimated / limit if limit else 0.0

        result: dict[str, Any] = {
            "estimated_tokens": estimated,
            "context_limit": limit,
            "warn_threshold": warn_t,
            "failover_threshold": failover_t,
            "utilization": utilization,
            "ratio": utilization,
            "model_id": resolved.profile_id,
            "resolved_target": resolved,
            "limit_basis": resolved.limit_basis,
            "context_window_kind": resolved.context_window_kind,
            "failover_model": None,
            "action": "pass",
        }

        if not self.enabled:
            return result

        if estimated >= failover_t:
            result["action"] = "reject"
            raise ContextGateError(estimated, limit, resolved.profile_id, utilization=utilization)
        elif estimated >= warn_t:
            result["action"] = "prune"

        return result

    def check_and_prune(
        self,
        blocks: list[dict[str, Any]],
        target: str | dict[str, Any] | ResolvedContextTarget,
        *,
        mandatory_key: str = "mandatory",
        priority_key: str = "priority",
        text_key: str = "text",
    ) -> list[dict[str, Any]]:
        """C3 §3.2 Fix: Prune droppable blocks until total tokens < warn_pct threshold.

        - Mandatory blocks are NEVER dropped.
        - Droppable blocks are dropped in ascending priority order (lowest priority dropped first).
        - Re-estimates exact pruned tokens after dropping each block.
        - Require resulting tokens strictly LESS THAN (<) target_tokens.
        - Fail closed (raise ContextGateError) if pruning cannot achieve < target_tokens.
        """
        resolved = self.resolve_target(target)
        limit = resolved.admission_limit
        # A 5% safety margin below warn_pct (restored from the pre-C3 code,
        # which this rewrite had dropped to warn_pct exactly): pruning to
        # land RIGHT AT the warn threshold means the very next similar-sized
        # ask immediately re-triggers pruning again -- empirically confirmed
        # during C3 cross-verification (a same-size follow-up query stayed
        # "pass" with the margin but flipped back to "prune" without it).
        target_tokens = int(limit * (self.warn_pct - 0.05))

        mandatory_blocks = [b for b in blocks if b.get(mandatory_key, False)]
        droppable_blocks = sorted([b for b in blocks if not b.get(mandatory_key, False)], key=lambda b: b.get(priority_key, 0))

        kept_mandatory = list(mandatory_blocks)
        kept_droppable = list(droppable_blocks)

        def _calc_total(mb: list[dict], db: list[dict]) -> int:
            txt = "".join(b.get(text_key, "") for b in mb + db)
            return estimate_tokens(txt)

        current_tokens = _calc_total(kept_mandatory, kept_droppable)
        if current_tokens < target_tokens:
            return kept_mandatory + kept_droppable

        for block in droppable_blocks:
            kept_droppable.remove(block)
            current_tokens = _calc_total(kept_mandatory, kept_droppable)
            if current_tokens < target_tokens:
                break

        if current_tokens >= target_tokens:
            raise ContextGateError(current_tokens, limit, resolved.profile_id, utilization=current_tokens / limit if limit else 0.0)

        return kept_mandatory + kept_droppable


def _main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="ContextGate v2.0 — token estimation tool")
    parser.add_argument("--model", default="ag.deepthink", help="Profile or Model ID to check against")
    parser.add_argument("--file", help="File to estimate (uses stdin if omitted)")
    parser.add_argument("--text", help="Text to estimate directly")
    args = parser.parse_args()

    if args.text:
        text = args.text
    elif args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    gate = ContextGate()
    try:
        result = gate.check(text, args.model)
    except ContextGateError as exc:
        result = {
            "action": "reject",
            "error": str(exc),
            "estimated_tokens": getattr(exc, "estimated_tokens", 0),
            "context_limit": getattr(exc, "context_limit", 0),
            "utilization": getattr(exc, "utilization", None),
        }

    util = result.get("utilization")
    pct_str = f"{util * 100:.1f}%" if isinstance(util, (int, float)) else "absent"
    print(f"Target    : {args.model}")
    print(f"Estimated : {result.get('estimated_tokens', 0):,} tokens ({pct_str})")
    print(f"Limit     : {result.get('context_limit', '?'):,}")
    print(f"Action    : {result.get('action', 'reject').upper()}")


if __name__ == "__main__":
    _main()
