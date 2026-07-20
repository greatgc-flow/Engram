"""hub_error.py — Taxonomy-driven error visibility layer (Phase 6).

Wraps error reporting with:
  - error-taxonomy.json tier classification
  - Korean console display (T2+)
  - hub_logging.py integration (error-log.jsonl)
  - governance_params.json: error_show_stacktrace, error_5whys_auto_log

Usage (standalone):
    from hub_error import HubError
    HubError.report("PEER_TIMEOUT", peer="gc", action="action_ask", message="180s timeout")

Usage (in hub.py action_report_error):
    HubError.report_from_legacy(peer, pattern, detail, severity)
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

_CORE_DIR = Path(__file__).parent
_SYS_DIR = _CORE_DIR.parent
_AI_DIR = _SYS_DIR / "ai"
_TAXONOMY_PATH = _AI_DIR / "error-taxonomy.json"
_GOVERNANCE_PATH = _AI_DIR / "governance_params.json"

# Tier display labels (Korean per console_format spec)
_TIER_LABELS: dict[str, str] = {
    "T0": "무시",
    "T1": "정보",
    "T2": "경고",
    "T3": "오류",
    "T4": "치명",
}

_SEP = "━" * 52


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


class HubError:
    """Entry point for all hub error reporting."""

    _taxonomy: dict | None = None
    _gov: dict | None = None

    @classmethod
    def _get_taxonomy(cls) -> dict:
        if cls._taxonomy is None:
            cls._taxonomy = _load_json(_TAXONOMY_PATH)
        return cls._taxonomy

    @classmethod
    def _get_gov(cls) -> dict:
        if cls._gov is None:
            cls._gov = _load_json(_GOVERNANCE_PATH)
        return cls._gov

    @classmethod
    def _error_cfg(cls, error_type: str) -> dict:
        return cls._get_taxonomy().get("errors", {}).get(error_type, {})

    @classmethod
    def _tier_cfg(cls, tier: str) -> dict:
        return cls._get_taxonomy().get("tiers", {}).get(tier, {})

    @classmethod
    def _whys_template(cls, key: str) -> list[str]:
        return cls._get_taxonomy().get("5whys_templates", {}).get(key, [])

    @classmethod
    def _show_stacktrace(cls) -> bool:
        return bool(cls._get_gov().get("error_show_stacktrace", True))

    @classmethod
    def _5whys_auto_log(cls) -> bool:
        return bool(cls._get_gov().get("error_5whys_auto_log", True))

    @classmethod
    def _escalate_after_n(cls) -> int:
        return int(cls._get_gov().get("error_escalate_after_n", 2))

    # ── Core report ──────────────────────────────────────────────────────────

    @classmethod
    def report(
        cls,
        error_type: str,
        *,
        peer: str | None = None,
        action: str | None = None,
        message: str = "",
        exc: BaseException | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Report an error through the taxonomy system.

        Returns the structured error record (also logs and displays it).
        """
        ecfg = cls._error_cfg(error_type)
        tier = ecfg.get("tier", "T2")
        tier_cfg = cls._tier_cfg(tier)
        whys_key = ecfg.get("5whys", "")
        whys = cls._whys_template(whys_key) if whys_key else []

        stack: str | None = None
        if exc and cls._show_stacktrace():
            stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

        record: dict[str, Any] = {
            "error_type": error_type,
            "tier": tier,
            "peer": peer,
            "action": action,
            "message": message,
            "stacktrace": stack,
            "5whys_template": whys_key or None,
        }
        if extra:
            record.update(extra)

        # Console display (T1+)
        if tier_cfg.get("console", False):
            cls._display(tier, error_type, peer, action, message, stack, whys)

        # Log to error-log.jsonl via hub_logging
        cls._log_error(record)

        # Halt on T4
        if tier_cfg.get("halt", False):
            print(f"\n[HUB] 치명적 오류 — 실행을 중단합니다. ({error_type})", file=sys.stderr)
            sys.exit(4)

        return record

    @classmethod
    def report_from_legacy(
        cls,
        peer: str,
        pattern: str,
        detail: str = "",
        severity: str = "warn",
    ) -> None:
        """Adapter for hub.py action_report_error() legacy calls."""
        # Map severity strings to error types where possible
        error_type = cls._severity_to_error_type(pattern, severity)
        cls.report(error_type, peer=peer, action=pattern, message=detail or pattern)

    @classmethod
    def _severity_to_error_type(cls, pattern: str, severity: str) -> str:
        """Best-effort map from legacy pattern/severity to taxonomy error type."""
        pattern_upper = pattern.upper().replace("-", "_")
        known = cls._get_taxonomy().get("errors", {})
        if pattern_upper in known:
            return pattern_upper
        # Fuzzy match
        for k in known:
            if k in pattern_upper or pattern_upper in k:
                return k
        severity_map = {"error": "HUB_INTERNAL", "warn": "PEER_TIMEOUT", "info": "PEER_REFUSAL"}
        return severity_map.get(severity, "HUB_INTERNAL")

    # ── Display ───────────────────────────────────────────────────────────────

    @classmethod
    def _display(
        cls,
        tier: str,
        error_type: str,
        peer: str | None,
        action: str | None,
        message: str,
        stacktrace: str | None,
        whys: list[str],
    ) -> None:
        label = _TIER_LABELS.get(tier, tier)
        peer_str = peer or "-"
        action_str = action or "-"
        remediation = cls._remediation_hint(error_type)

        print(f"\n{_SEP}", file=sys.stderr)
        print(f"  {label} ({tier}) — {error_type}", file=sys.stderr)
        print(f"{_SEP}", file=sys.stderr)
        print(f"  피어   : {peer_str}", file=sys.stderr)
        print(f"  작업   : {action_str}", file=sys.stderr)
        print(f"  원인   : {message}", file=sys.stderr)
        if remediation:
            remediation = remediation.replace("{peer}", peer_str)
            print(f"  해결   : {remediation}", file=sys.stderr)
        if stacktrace and cls._show_stacktrace():
            print(f"\n  [스택트레이스]", file=sys.stderr)
            for line in stacktrace.strip().splitlines():
                print(f"    {line}", file=sys.stderr)
        if whys and cls._5whys_auto_log():
            print(f"\n  [5 Whys 점검]", file=sys.stderr)
            for i, q in enumerate(whys, 1):
                print(f"    {i}. {q}", file=sys.stderr)
        print(f"{_SEP}\n", file=sys.stderr)

    @classmethod
    def _remediation_hint(cls, error_type: str) -> str:
        _HINTS: dict[str, str] = {
            "PEER_TIMEOUT":         "hub.py health-check --peer {peer} → hub.py ask --to {peer} 재시도",
            "PEER_RATE_LIMIT":      "cost-log.jsonl 확인 → 대기 후 재시도 또는 fallback 피어 사용",
            "PEER_RED_GATE":        "hub.py peer-recover --peer {peer} → health.json 확인",
            "CONFIG_NOT_FOUND":     "infra.json config_registry 확인 → workspace-init 실행",
            "CONFIG_INVALID":       "JSON 파서로 파일 검증 → 백업에서 복원",
            "CONTEXT_GATE_REJECT":  "컨텍스트 축소 후 재시도 → hub_context.py --model {peer} --file 로 추정",
            "CONSENSUS_DEADLOCK":   "사용자 개입 필요 — proposal 재작성 또는 tiebreak 규칙 적용",
            "INV_VIOLATION":        "10-invariants.md 확인 → 해당 INV 번호 근거 재검토",
            "DOCS_MECE_FAIL":       "check_docs_mece.py 실행 → 실패 CHK-ID 수정",
            "HUB_INTERNAL":         "hub.py --debug 로 재실행 → error-log.jsonl 에서 스택 확인",
        }
        return _HINTS.get(error_type, "")

    # ── Logging ───────────────────────────────────────────────────────────────

    @classmethod
    def _log_error(cls, record: dict[str, Any]) -> None:
        """Write to error-log.jsonl via hub_logging if available."""
        try:
            from hub_logging import HubLogger
            logger = HubLogger()
            logger.log_error(
                error_type=record.get("error_type", "HUB_INTERNAL"),
                tier=record.get("tier", "T2"),
                peer=record.get("peer"),
                action=record.get("action"),
                message=record.get("message", ""),
                stacktrace=record.get("stacktrace"),
                whys_template=record.get("5whys_template"),
            )
        except Exception:
            pass  # logging failure must not propagate


# ── Convenience wrappers ──────────────────────────────────────────────────────

def report_error(
    error_type: str,
    *,
    peer: str | None = None,
    action: str | None = None,
    message: str = "",
    exc: BaseException | None = None,
) -> dict:
    """Module-level shortcut for HubError.report()."""
    return HubError.report(error_type, peer=peer, action=action, message=message, exc=exc)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="hub_error — taxonomy-driven error reporter")
    parser.add_argument("error_type", help="Error type from error-taxonomy.json")
    parser.add_argument("--peer", default=None)
    parser.add_argument("--action", default=None)
    parser.add_argument("--message", default="test error")
    parser.add_argument("--list-types", action="store_true", help="List all known error types")
    args = parser.parse_args()

    if args.list_types:
        taxonomy = _load_json(_TAXONOMY_PATH)
        for etype, ecfg in taxonomy.get("errors", {}).items():
            print(f"  {etype:<30} tier={ecfg.get('tier')} category={ecfg.get('category')}")
        return

    HubError.report(args.error_type, peer=args.peer, action=args.action, message=args.message)


if __name__ == "__main__":
    _main()
