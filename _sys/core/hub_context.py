"""hub_context.py — ContextGate v1.0: token estimation and context pruning.

Algorithm:
  1. Estimate input tokens (CJK-aware)
  2. If >= warn_pct (80%): prune low-priority blocks
  3. If >= failover_pct (95%): route to smaller model; raise CONTEXT_GATE_REJECT if none

Config: _sys/ai/governance_params.json (context_gate_* keys)
Model limits: _sys/ai/model-registry.json (context_limit per model)
Traceability: _sys/ai/traceability_map.json entry "context-gate"

Usage:
    from hub_context import ContextGate
    gate = ContextGate()
    result = gate.check(text, model_id="claude-sonnet-4-6")
    # result: {"action": "pass"|"prune"|"failover"|"reject", "estimated_tokens": N, ...}
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

_CORE_DIR = Path(__file__).parent
_SYS_DIR = _CORE_DIR.parent
_AI_DIR = _SYS_DIR / "ai"
_GOVERNANCE_PATH = _AI_DIR / "governance_params.json"
_MODEL_REGISTRY_PATH = _AI_DIR / "model-registry.json"

# Fallback model chains when primary context is exceeded
_FAILOVER_CHAIN: dict[str, str] = {
    "claude-opus-4-8":        "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6":      "claude-haiku-4-5-20251001",
    "claude-fable-5":         "claude-haiku-4-5-20251001",
    "claude-opus-4-7":        "claude-haiku-4-5-20251001",
    "gemini-3-pro":           "gemini-3-flash",
    "gemini-3.1-pro":         "gemini-3-flash",
    "gemini-2.5-pro":         "gemini-3-flash",
    "gpt-5.5":                "gpt-5.4-mini",
    "gpt-5.4":                "gpt-5.4-mini",
    "o3-pro":                 "gpt-5.4-mini",
    "o3":                     "gpt-5.4-mini",
}


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
    """Estimate token count. CJK text uses 1.8× multiplier (tokens ≈ chars/2)."""
    if not text:
        return 0
    ratio = _cjk_ratio(text)
    if ratio >= 0.20:
        return int(len(text) / 2 * 1.8)
    return int(len(text) / 3.5)


class ContextGateError(RuntimeError):
    """Raised when context cannot be reduced and no failover model is available."""
    def __init__(self, estimated_tokens: int, context_limit: int, model_id: str) -> None:
        super().__init__(
            f"CONTEXT_GATE_REJECT: {estimated_tokens} estimated tokens exceeds "
            f"{int(context_limit * 0.95):.0f} failover threshold "
            f"for model {model_id} (limit={context_limit})"
        )
        self.estimated_tokens = estimated_tokens
        self.context_limit = context_limit
        self.model_id = model_id
        self.error_type = "CONTEXT_GATE_REJECT"
        self.tier = "T2"


class ContextGate:
    """Config-driven context gate. Estimates token usage and decides action."""

    def __init__(
        self,
        governance_path: Path | None = None,
        registry_path: Path | None = None,
    ) -> None:
        self._gov = self._load_json(governance_path or _GOVERNANCE_PATH)
        self._registry = self._load_json(registry_path or _MODEL_REGISTRY_PATH)

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_json(self, path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    @property
    def enabled(self) -> bool:
        return bool(self._gov.get("context_gate_enabled", True))

    @property
    def warn_pct(self) -> float:
        return float(self._gov.get("context_gate_warn_pct", 0.80))

    @property
    def failover_pct(self) -> float:
        return float(self._gov.get("context_gate_failover_pct", 0.95))

    def context_limit(self, model_id: str) -> int:
        """Return context_limit for model_id from model-registry.json."""
        models = self._registry.get("models", {})
        model = models.get(model_id, {})
        return int(model.get("context_limit", 200_000))

    # ── Core check ────────────────────────────────────────────────────────────

    def check(self, text: str, model_id: str) -> dict[str, Any]:
        """Evaluate text length against model context limit.

        Returns dict with keys:
            action: "pass" | "prune" | "failover" | "reject"
            estimated_tokens: int
            context_limit: int
            warn_threshold: int
            failover_threshold: int
            utilization: float (0.0–1.0+)
            failover_model: str | None
        """
        estimated = estimate_tokens(text)
        limit = self.context_limit(model_id)
        warn_t = int(limit * self.warn_pct)
        failover_t = int(limit * self.failover_pct)

        result: dict[str, Any] = {
            "estimated_tokens": estimated,
            "context_limit": limit,
            "warn_threshold": warn_t,
            "failover_threshold": failover_t,
            "utilization": estimated / limit if limit else 0.0,
            "model_id": model_id,
            "failover_model": None,
            "action": "pass",
        }

        if not self.enabled:
            return result

        if estimated >= failover_t:
            failover_model = _FAILOVER_CHAIN.get(model_id)
            if failover_model:
                result["action"] = "failover"
                result["failover_model"] = failover_model
            else:
                result["action"] = "reject"
                raise ContextGateError(estimated, limit, model_id)
        elif estimated >= warn_t:
            result["action"] = "prune"

        return result

    def check_and_prune(
        self,
        blocks: list[dict[str, Any]],
        model_id: str,
        *,
        priority_key: str = "priority",
        text_key: str = "text",
    ) -> list[dict[str, Any]]:
        """Prune lowest-priority blocks until total estimate is below warn_pct.

        Each block must have `text_key` (str) and optionally `priority_key` (int, lower=lower priority).
        Returns the subset of blocks that fit within the threshold.
        """
        limit = self.context_limit(model_id)
        target = int(limit * (self.warn_pct - 0.05))

        sorted_blocks = sorted(blocks, key=lambda b: b.get(priority_key, 0))
        kept: list[dict[str, Any]] = list(blocks)

        full_text = "".join(b.get(text_key, "") for b in kept)
        if estimate_tokens(full_text) <= target:
            return kept

        for block in sorted_blocks:
            if block in kept:
                kept.remove(block)
            remaining = "".join(b.get(text_key, "") for b in kept)
            if estimate_tokens(remaining) <= target:
                break

        return kept


# ── CLI ───────────────────────────────────────────────────────────────────────

def _main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="ContextGate v1.0 — token estimation tool")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Model ID to check against")
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
            "estimated_tokens": exc.estimated_tokens,
            "context_limit": exc.context_limit,
        }

    pct = result.get("utilization", 0) * 100
    print(f"Model     : {args.model}")
    print(f"Estimated : {result['estimated_tokens']:,} tokens ({pct:.1f}%)")
    print(f"Limit     : {result.get('context_limit', '?'):,}")
    print(f"Action    : {result['action'].upper()}")
    if result.get("failover_model"):
        print(f"Failover  : {result['failover_model']}")


if __name__ == "__main__":
    _main()
