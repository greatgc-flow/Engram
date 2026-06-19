"""hub_logging.py — 7-type structured logging with rolling policy.

Config: _sys/ai/logging-config.json
Types: ipc-log, console-log, cost-log, error-log, reasoning-log, model-drift, self-care-log

Usage:
    from hub_logging import HubLogger
    logger = HubLogger()
    logger.log_ipc(peer_id="gc", direction="send", query_file="...", query_preview="...")
    logger.log_error(error_type="PEER_TIMEOUT", tier="T2", peer="gc", message="timeout")
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CORE_DIR = Path(__file__).parent
_SYS_DIR = _CORE_DIR.parent
_AI_DIR = _SYS_DIR / "ai"
_CONFIG_PATH = _AI_DIR / "logging-config.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class HubLogger:
    """Config-driven structured logger for all 7 hub log types."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._cfg = self._load_config(config_path or _CONFIG_PATH)
        self._log_dir = _SYS_DIR.parent / self._cfg.get("log_dir", "_sys/data/logs")
        self._log_dir.mkdir(parents=True, exist_ok=True)

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self, path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"types": {}, "rolling": {}}

    def _type_cfg(self, log_type: str) -> dict:
        return self._cfg.get("types", {}).get(log_type, {})

    # ── Core write ────────────────────────────────────────────────────────────

    def _write(self, log_type: str, record: dict) -> None:
        """Append record as JSONL line; trigger rolling check."""
        tcfg = self._type_cfg(log_type)
        filename = tcfg.get("file", f"{log_type}.jsonl")
        log_path = self._log_dir / filename

        record.setdefault("ts", _now_iso())
        record["_type"] = log_type

        try:
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            print(f"[hub_logging] write error ({log_type}): {exc}", file=sys.stderr)
            return

        self._maybe_roll(log_type, log_path, tcfg)

    # ── Rolling ───────────────────────────────────────────────────────────────

    def _maybe_roll(self, log_type: str, log_path: Path, tcfg: dict) -> None:
        max_mb = tcfg.get("max_mb")
        if max_mb is None:
            return
        try:
            size_mb = log_path.stat().st_size / (1024 * 1024)
        except OSError:
            return
        if size_mb >= max_mb:
            self._roll(log_type, log_path)

    def _roll(self, log_type: str, log_path: Path) -> None:
        rolling_cfg = self._cfg.get("rolling", {})
        archive_dir = self._log_dir / rolling_cfg.get("archive_dir", "archive")
        archive_dir.mkdir(parents=True, exist_ok=True)

        fmt = rolling_cfg.get("archive_format", "{name}-{date}.jsonl.gz")
        archive_name = fmt.format(name=log_type, date=_today())
        archive_path = archive_dir / archive_name

        compress = rolling_cfg.get("compress", True)
        try:
            if compress:
                with log_path.open("rb") as src, gzip.open(str(archive_path), "wb") as dst:
                    shutil.copyfileobj(src, dst)
            else:
                shutil.copy2(str(log_path), str(archive_path))
            log_path.unlink()
        except OSError as exc:
            print(f"[hub_logging] roll error ({log_type}): {exc}", file=sys.stderr)

    # ── Public log methods ────────────────────────────────────────────────────

    def log_ipc(
        self,
        *,
        peer_id: str,
        direction: str,
        query_file: str | None = None,
        query_preview: str = "",
        response_preview: str | None = None,
        elapsed_sec: float | None = None,
        success: bool = True,
    ) -> None:
        """IPC send/receive record (captures before query file deletion)."""
        self._write("ipc-log", {
            "direction": direction,
            "peer_id": peer_id,
            "query_file": query_file,
            "query_preview": query_preview[:500],
            "response_preview": (response_preview or "")[:500],
            "elapsed_sec": elapsed_sec,
            "success": success,
        })

    def log_console(self, *, channel: str = "user", message: str, level: str = "INFO") -> None:
        """Console output record (user/system/debug)."""
        self._write("console-log", {
            "channel": channel,
            "level": level,
            "message": message,
        })

    def log_cost(
        self,
        *,
        peer_id: str,
        model_id: str,
        profile_id: str | None = None,
        task_type: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        reasoning_tokens: int | None = None,
        cost_usd: float | None = None,
        quality_score: float | None = None,
        latency_sec: float | None = None,
        success: bool = True,
    ) -> None:
        """Per-ask cost, quality, latency record."""
        self._write("cost-log", {
            "peer_id": peer_id,
            "model_id": model_id,
            "profile_id": profile_id,
            "task_type": task_type,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "cost_usd": cost_usd,
            "quality_score": quality_score,
            "latency_sec": latency_sec,
            "success": success,
        })

    def log_error(
        self,
        *,
        error_type: str,
        tier: str,
        peer: str | None = None,
        action: str | None = None,
        message: str,
        stacktrace: str | None = None,
        whys_template: str | None = None,
    ) -> None:
        """T2+ error record with 5-Whys template reference."""
        self._write("error-log", {
            "error_type": error_type,
            "tier": tier,
            "peer": peer,
            "action": action,
            "message": message,
            "stacktrace": stacktrace,
            "5whys_template": whys_template,
            "resolved": False,
        })

    def log_reasoning(
        self,
        *,
        peer_id: str,
        model_id: str,
        reasoning_tokens: int,
        budget_requested: int | None = None,
        effort_level: str | None = None,
    ) -> None:
        """Extended thinking / reasoning token usage record."""
        self._write("reasoning-log", {
            "peer_id": peer_id,
            "model_id": model_id,
            "reasoning_tokens": reasoning_tokens,
            "budget_requested": budget_requested,
            "effort_level": effort_level,
        })

    def log_token_calibration(
        self,
        *,
        peer_id: str,
        model_id: str,
        estimated_tokens: int,
        actual_prompt_tokens: int | None,
        actual_completion_tokens: int | None,
        actual_reasoning_tokens: int | None,
        ipc_protocol_version: int | None = None,
    ) -> None:
        """Calibration record comparing static token estimate vs actual API usage.

        Only written when actual_reasoning_tokens is not None (i.e., output_tokens_details present).
        Used to improve estimate_tokens() accuracy over time (TM-04).
        Logged to: data/logs/token_calibration.jsonl
        """
        if actual_reasoning_tokens is None:
            return
        record = {
            "ts": _now_iso(),
            "_type": "token_calibration",
            "peer_id": peer_id,
            "model_id": model_id,
            "estimated_tokens": estimated_tokens,
            "actual_reasoning_tokens": actual_reasoning_tokens,
            "prompt_tokens": actual_prompt_tokens,
            "completion_tokens": actual_completion_tokens,
            "ipc_protocol_version": ipc_protocol_version,
        }
        # Write to data/logs/ (sibling of the normal log dir) for separation
        calib_path = self._log_dir.parent / "logs" / "token_calibration.jsonl"
        try:
            calib_path.parent.mkdir(parents=True, exist_ok=True)
            with calib_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            print(f"[hub_logging] token_calibration write error: {exc}", file=sys.stderr)

    def log_model_drift(
        self,
        *,
        model_id: str,
        field: str,
        expected: Any,
        actual: Any,
        source: str = "model-registry.json",
    ) -> None:
        """model-registry.json validation failure record."""
        self._write("model-drift", {
            "model_id": model_id,
            "field": field,
            "expected": expected,
            "actual": actual,
            "source": source,
        })

    def log_self_care(
        self,
        *,
        trigger: str,
        step: str,
        status: str,
        detail: str = "",
        duration_sec: float | None = None,
    ) -> None:
        """self_care.py phase execution result."""
        self._write("self-care-log", {
            "trigger": trigger,
            "step": step,
            "status": status,
            "detail": detail,
            "duration_sec": duration_sec,
        })


# ── CLI ───────────────────────────────────────────────────────────────────────

def _main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Hub logging test/inspect tool")
    sub = parser.add_subparsers(dest="cmd")

    t = sub.add_parser("test", help="Write one test record per log type")
    sub.add_parser("status", help="Show log file sizes")

    args = parser.parse_args()
    logger = HubLogger()

    if args.cmd == "test":
        logger.log_ipc(peer_id="gc", direction="send", query_preview="test query")
        logger.log_console(message="test console output")
        logger.log_cost(peer_id="gc", model_id="gemini-2.5-pro", cost_usd=0.001, success=True)
        logger.log_error(error_type="PEER_TIMEOUT", tier="T2", peer="gc", message="test timeout")
        logger.log_reasoning(peer_id="cc", model_id="claude-sonnet-4-6", reasoning_tokens=1024)
        logger.log_model_drift(model_id="gemini-2.5-pro", field="output_limit", expected=24576, actual=65536)
        logger.log_self_care(trigger="manual", step="test", status="OK")
        print("[hub_logging] test records written to", logger._log_dir)
    elif args.cmd == "status":
        for log_type, tcfg in logger._cfg.get("types", {}).items():
            path = logger._log_dir / tcfg.get("file", f"{log_type}.jsonl")
            size = f"{path.stat().st_size / 1024:.1f}KB" if path.exists() else "missing"
            max_mb = tcfg.get("max_mb", "∞")
            print(f"  {log_type:<16} {size:>10}  (max {max_mb}MB)")
    else:
        parser.print_help()


if __name__ == "__main__":
    _main()
