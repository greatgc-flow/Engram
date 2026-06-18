"""Benchmark I — Adapter parse_output fuzz test.

Feeds each adapter (Gemini, Codex, Claude) with malformed, empty, truncated,
and edge-case inputs. Verifies exception handling completeness.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from hub_peer import BaseAdapter  # noqa: E402

# Dynamically import adapter classes
import importlib
hub_peer = importlib.import_module("hub_peer")

ADAPTER_CLASSES = {}
for name in dir(hub_peer):
    obj = getattr(hub_peer, name)
    try:
        if (isinstance(obj, type) and issubclass(obj, BaseAdapter)
                and obj is not BaseAdapter):
            ADAPTER_CLASSES[name] = obj
    except TypeError:
        pass

# Fuzz cases: (label, stdout_content)
FUZZ_CASES: list[tuple[str, str]] = [
    ("empty",            ""),
    ("whitespace",       "   \n  \t  "),
    ("null_bytes",       "hello\x00world\x00"),
    ("lone_newline",     "\n"),
    ("valid_short",      "Hello, I am a peer response."),
    ("valid_long",       "A" * 50_000),
    ("unicode_heavy",    "가나다라마바사아자차카타파하" * 1000),
    ("json_fragment",    '{"text": "partial json without closing'),
    ("valid_json",       '{"output": "test response", "usage": {"input_tokens": 100, "output_tokens": 50}}'),
    ("json_with_usage",  '{"output": "ok", "usage": {"input_tokens": 200, "output_tokens": 80, "output_tokens_details": {"reasoning_tokens": 40}}}'),
    ("binary_garbage",   bytes(range(256)).decode("latin-1")),
    ("html_tags",        "<html><body><p>Oops, got HTML instead of JSON</p></body></html>"),
    ("error_message",    "Error: rate limit exceeded\nRetry after 60 seconds"),
    ("ansi_codes",       "\x1b[31mError\x1b[0m: something went wrong"),
    ("markdown",         "# Response\n\nThis is **bold** text.\n```python\nx = 1\n```"),
    ("repeat_newlines",  "\n" * 1000),
    ("mixed_encoding",   "Hello 世界 مرحبا привет 🌍"),
    ("very_large",       "x" * 5_000_000),
    ("truncated_json",   '{"usage": {"input_tok'),
    ("nested_json",      '{"outer": {"inner": {"deep": {"value": 42}}}, "output": "ok"}'),
]

# Node configs to test with (include --json flag for Codex)
NODE_CONFIGS = [
    {},
    {"invoke_args": ["--json"]},
    {"invoke_args": ["--no-stream"]},
    {"peer": "gc", "model": "gemini-3-pro"},
]


def run_fuzz(adapter_name: str, adapter_cls: type, case_label: str,
             stdout: str, node: dict) -> dict:
    """Run both parse_output and extract_usage, catch all exceptions."""
    result = {
        "adapter": adapter_name,
        "case": case_label,
        "node_args": str(node.get("invoke_args", [])),
        "parse_ok": False,
        "parse_result_len": 0,
        "parse_exc": None,
        "usage_ok": False,
        "usage_keys": [],
        "usage_exc": None,
    }

    adapter = adapter_cls()

    # Test parse_output
    try:
        parsed = adapter.parse_output(stdout, node)
        result["parse_ok"] = True
        result["parse_result_len"] = len(parsed) if parsed else 0
    except Exception as e:
        result["parse_exc"] = type(e).__name__

    # Test extract_usage
    try:
        usage = adapter.extract_usage(stdout, node)
        result["usage_ok"] = True
        result["usage_keys"] = list(usage.keys()) if usage else []
    except Exception as e:
        result["usage_exc"] = type(e).__name__

    return result


# ── Main ─────────────────────────────────────────────────────────────────────

print("=" * 90)
print(f"  BENCHMARK I — Adapter parse_output fuzz test")
print(f"  Adapters found: {list(ADAPTER_CLASSES.keys())}")
print(f"  Fuzz cases: {len(FUZZ_CASES)}  |  Node configs: {len(NODE_CONFIGS)}")
print(f"  Total tests: {len(ADAPTER_CLASSES) * len(FUZZ_CASES) * len(NODE_CONFIGS)}")
print("=" * 90)
print()

all_results = []
for adapter_name, adapter_cls in sorted(ADAPTER_CLASSES.items()):
    adapter_results = []
    for case_label, stdout in FUZZ_CASES:
        for node in NODE_CONFIGS:
            r = run_fuzz(adapter_name, adapter_cls, case_label, stdout, node)
            adapter_results.append(r)
    all_results.extend(adapter_results)

    parse_failures = [r for r in adapter_results if not r["parse_ok"]]
    usage_failures = [r for r in adapter_results if not r["usage_ok"]]
    parse_ok_count = sum(1 for r in adapter_results if r["parse_ok"])
    usage_ok_count = sum(1 for r in adapter_results if r["usage_ok"])
    total = len(adapter_results)

    print(f"  {adapter_name}")
    print(f"    parse_output : {parse_ok_count}/{total} OK  "
          f"({len(parse_failures)} exceptions)")
    print(f"    extract_usage: {usage_ok_count}/{total} OK  "
          f"({len(usage_failures)} exceptions)")

    if parse_failures:
        by_exc = {}
        for r in parse_failures:
            by_exc.setdefault(r["parse_exc"], []).append(r["case"])
        for exc, cases in sorted(by_exc.items()):
            print(f"    parse FAIL [{exc}]: {', '.join(cases[:5])}"
                  + ("..." if len(cases) > 5 else ""))

    if usage_failures:
        by_exc = {}
        for r in usage_failures:
            by_exc.setdefault(r["usage_exc"], []).append(r["case"])
        for exc, cases in sorted(by_exc.items()):
            print(f"    usage FAIL [{exc}]: {', '.join(cases[:5])}"
                  + ("..." if len(cases) > 5 else ""))

    # Check silent corruption: parse succeeded but returned empty on non-empty input
    silent_empty = [r for r in adapter_results
                    if r["parse_ok"] and r["parse_result_len"] == 0
                    and r["case"] not in ("empty", "whitespace", "lone_newline", "repeat_newlines")]
    if silent_empty:
        print(f"    WARNING: {len(silent_empty)} cases returned empty string on non-empty input")
        for r in silent_empty[:3]:
            print(f"      case={r['case']} node_args={r['node_args']}")
    print()

# ── Summary ──────────────────────────────────────────────────────────────────

print("=" * 90)
print("  OVERALL FUZZ SUMMARY")
print("=" * 90)

total_all = len(all_results)
parse_exc_total = sum(1 for r in all_results if not r["parse_ok"])
usage_exc_total = sum(1 for r in all_results if not r["usage_ok"])

print(f"  Total test cases      : {total_all}")
print(f"  parse_output failures : {parse_exc_total} ({parse_exc_total/total_all*100:.1f}%)")
print(f"  extract_usage failures: {usage_exc_total} ({usage_exc_total/total_all*100:.1f}%)")
print()

# Exception type breakdown
from collections import Counter
parse_excs = Counter(r["parse_exc"] for r in all_results if r["parse_exc"])
usage_excs = Counter(r["usage_exc"] for r in all_results if r["usage_exc"])

if parse_excs:
    print("  parse_output exception types:")
    for exc, cnt in parse_excs.most_common():
        print(f"    {exc}: {cnt}")
if usage_excs:
    print("  extract_usage exception types:")
    for exc, cnt in usage_excs.most_common():
        print(f"    {exc}: {cnt}")

if not parse_excs and not usage_excs:
    print("  All adapters handled all fuzz inputs without exceptions — ROBUST")

print()
print("  Done.")
