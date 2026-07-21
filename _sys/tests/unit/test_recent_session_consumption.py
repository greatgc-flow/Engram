"""TDD for the pretdd-prep-2026-07-21-diag-quota-metrics.md Topic 3 design:
Recent session token consumption telemetry instrumentation and aggregation logic.
"""
import sys
import json
import inspect
from pathlib import Path
from typing import Any
import pytest

# Set import paths for _sys/core and _sys/cli
SYS_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SYS_DIR / "core"))
sys.path.insert(0, str(SYS_DIR / "cli"))

from hub_logging import HubLogger
import hub_peer
import diag


# ── 1. Log Cost Signature and Serialization Tests ────────────────────────────

def test_log_cost_signature_introspection():
    """Verify that log_cost signature contains the new parameters as keyword-only arguments with default None."""
    sig = inspect.signature(HubLogger.log_cost)

    # New params: ask_id, session_id, turn_id, token_scope
    for param_name in ["ask_id", "session_id", "turn_id", "token_scope"]:
        assert param_name in sig.parameters
        param = sig.parameters[param_name]
        assert param.kind == inspect.Parameter.KEYWORD_ONLY
        assert param.default is None


def test_old_signature_log_cost_succeeds_and_writes_null_keys(tmp_path, monkeypatch):
    """Old-signature calls must still succeed, and they should serialize the new keys as null."""
    monkeypatch.setenv("HUB_LOG_DIR", str(tmp_path / "hub-logs"))
    logger = HubLogger()

    # Call with old signature only
    logger.log_cost(
        peer_id="cc",
        model_id="claude-3-5",
        input_tokens=100,
        output_tokens=20,
    )

    cost_log_file = tmp_path / "hub-logs" / "cost-log.jsonl"
    assert cost_log_file.exists()

    lines = cost_log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])

    # Check that new keys are explicitly written as null/None
    for key in ["ask_id", "session_id", "turn_id", "token_scope"]:
        assert key in row
        assert row[key] is None


def test_new_identifiers_serialize_unchanged(tmp_path, monkeypatch):
    """New identifiers passed to log_cost must be written to cost-log.jsonl exactly as supplied."""
    monkeypatch.setenv("HUB_LOG_DIR", str(tmp_path / "hub-logs"))
    logger = HubLogger()

    logger.log_cost(
        peer_id="cx",
        model_id="gpt-5",
        ask_id="ask-12345",
        session_id="sess-67890",
        turn_id="turn-555",
        token_scope="turn",
        input_tokens=200,
        output_tokens=50,
    )

    cost_log_file = tmp_path / "hub-logs" / "cost-log.jsonl"
    row = json.loads(cost_log_file.read_text(encoding="utf-8").splitlines()[0])

    assert row["ask_id"] == "ask-12345"
    assert row["session_id"] == "sess-67890"
    assert row["turn_id"] == "turn-555"
    assert row["token_scope"] == "turn"


# ── 2. Codex Provider Rule Tests ──────────────────────────────────────────────

def test_codex_producer_selects_last_token_usage_never_total():
    """Verify that Codex adapter extract_usage parses last_token_usage correctly.
    It should not sum cached_input_tokens if it's already subset (unlike Anthropic's additive shape),
    and should not double-count reasoning tokens which are a subset of output_tokens.
    """
    adapter = hub_peer.CodexAdapter()
    node = {"invoke_args": ["exec", "--json"]}

    # Raw stdout simulating a Codex rollout event stream containing last_token_usage
    raw_stdout = json.dumps({
        "type": "token_count",
        "info": {
            "total_token_usage": {
                "input_tokens": 18067014,
                "cached_input_tokens": 17251072,
                "output_tokens": 60132,
                "reasoning_output_tokens": 32186,
                "total_tokens": 18127146
            },
            "last_token_usage": {
                "input_tokens": 162059,
                "cached_input_tokens": 160512,
                "output_tokens": 255,
                "reasoning_output_tokens": 94,
                "total_tokens": 162314
            }
        }
    })

    usage = adapter.extract_usage(raw_stdout, node, session_id="some-session")

    # We must only extract from last_token_usage:
    # input_tokens = 162059 (cached_input_tokens 160512 is not added)
    # output_tokens = 255
    # reasoning_tokens = 94 (not added or double counted)
    assert usage["input_tokens"] == 162059
    assert usage["output_tokens"] == 255
    assert usage["reasoning_tokens"] == 94
    assert usage.get("token_scope") == "turn"


# ── 3. Aggregation Engine Tests ───────────────────────────────────────────────

def test_aggregation_same_session_across_asks_groups_together(tmp_path):
    """Multiple asks belonging to the same session must group together and sum correctly."""
    cost_log = tmp_path / "cost-log.jsonl"
    cost_log.write_text("\n".join([
        json.dumps({
            "ts": "2026-07-21T10:00:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t1", "input_tokens": 100, "output_tokens": 20
        }),
        json.dumps({
            "ts": "2026-07-21T10:01:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t2", "input_tokens": 150, "output_tokens": 30
        }),
    ]), encoding="utf-8")

    res = diag.load_recent_session_consumption(cost_log)
    assert len(res) == 1
    session = res[0]
    assert session["peer"] == "cx"
    assert session["session_id"] == "sess-1"
    assert session["input_tokens"] == 250
    assert session["output_tokens"] == 50
    assert session["total_tokens"] == 300


def test_aggregation_groups_by_root_peer_id(tmp_path):
    """Rows with sub-peer IDs (e.g. 'cx.deepthink' and 'cx.standard') must group under the root peer ID ('cx')."""
    cost_log = tmp_path / "cost-log.jsonl"
    cost_log.write_text("\n".join([
        json.dumps({
            "ts": "2026-07-21T10:00:00Z", "peer_id": "cx.deepthink", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t1", "input_tokens": 100, "output_tokens": 20
        }),
        json.dumps({
            "ts": "2026-07-21T10:01:00Z", "peer_id": "cx.standard", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t2", "input_tokens": 150, "output_tokens": 30
        }),
    ]), encoding="utf-8")

    res = diag.load_recent_session_consumption(cost_log)
    assert len(res) == 1
    assert res[0]["peer"] == "cx"
    assert res[0]["session_id"] == "sess-1"
    assert res[0]["input_tokens"] == 250


def test_aggregation_same_session_different_peers_do_not_collide(tmp_path):
    """The same session_id value used by different peers must produce separate group rows."""
    cost_log = tmp_path / "cost-log.jsonl"
    cost_log.write_text("\n".join([
        json.dumps({
            "ts": "2026-07-21T10:00:00Z", "peer_id": "cc", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-shared", "turn_id": "t1", "input_tokens": 100, "output_tokens": 20
        }),
        json.dumps({
            "ts": "2026-07-21T10:01:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-shared", "turn_id": "t2", "input_tokens": 150, "output_tokens": 30
        }),
    ]), encoding="utf-8")

    res = diag.load_recent_session_consumption(cost_log)
    assert len(res) == 2
    ids = {(r["peer"], r["session_id"]) for r in res}
    assert ids == {("cc", "sess-shared"), ("cx", "sess-shared")}


def test_aggregation_sessionless_asks_group_by_ask_id(tmp_path):
    """Asks that lack a session_id but have an ask_id must group individually as 'ask:ASK_ID'."""
    cost_log = tmp_path / "cost-log.jsonl"
    cost_log.write_text("\n".join([
        json.dumps({
            "ts": "2026-07-21T10:00:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "ask_id": "ask-a", "input_tokens": 50, "output_tokens": 10
        }),
        json.dumps({
            "ts": "2026-07-21T10:01:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "ask_id": "ask-b", "input_tokens": 80, "output_tokens": 15
        }),
    ]), encoding="utf-8")

    res = diag.load_recent_session_consumption(cost_log)
    assert len(res) == 2
    session_keys = {r["session_id"] for r in res}
    assert session_keys == {"ask:ask-a", "ask:ask-b"}


def test_aggregation_legacy_idless_rows_excluded(tmp_path):
    """Rows lacking both session_id and ask_id are legacy/unattributed and must be excluded."""
    cost_log = tmp_path / "cost-log.jsonl"
    cost_log.write_text("\n".join([
        json.dumps({
            "ts": "2026-07-21T10:00:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t1", "input_tokens": 100, "output_tokens": 20
        }),
        # Legacy row (no session_id, no ask_id)
        json.dumps({
            "ts": "2026-07-21T10:01:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "input_tokens": 500, "output_tokens": 100
        }),
    ]), encoding="utf-8")

    res = diag.load_recent_session_consumption(cost_log)
    assert len(res) == 1
    assert res[0]["session_id"] == "sess-1"
    assert res[0]["input_tokens"] == 100


def test_aggregation_duplicate_turn_or_ask_id_is_last_write_wins(tmp_path):
    """Duplicate turn_id or ask_id within a group must resolve as last-write-wins (by latest ts+line)."""
    cost_log = tmp_path / "cost-log.jsonl"
    cost_log.write_text("\n".join([
        json.dumps({
            "ts": "2026-07-21T10:00:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t1", "input_tokens": 100, "output_tokens": 20
        }),
        # Duplicate t1 with later timestamp (wins)
        json.dumps({
            "ts": "2026-07-21T10:00:30Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t1", "input_tokens": 120, "output_tokens": 25
        }),
        # Duplicate t1 with same timestamp but later line (wins)
        json.dumps({
            "ts": "2026-07-21T10:00:30Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t1", "input_tokens": 130, "output_tokens": 28
        }),
        json.dumps({
            "ts": "2026-07-21T10:01:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t2", "input_tokens": 50, "output_tokens": 10
        }),
    ]), encoding="utf-8")

    res = diag.load_recent_session_consumption(cost_log)
    assert len(res) == 1
    # 130 (latest t1) + 50 (t2) = 180
    assert res[0]["input_tokens"] == 180
    # 28 (latest t1) + 10 (t2) = 38
    assert res[0]["output_tokens"] == 38


def test_aggregation_cumulative_only_group_uses_latest_snapshot(tmp_path):
    """Groups containing only session_cumulative rows must not sum them, but use the latest snapshot."""
    cost_log = tmp_path / "cost-log.jsonl"
    cost_log.write_text("\n".join([
        json.dumps({
            "ts": "2026-07-21T10:00:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "session_cumulative",
            "session_id": "sess-1", "turn_id": "t1", "input_tokens": 100, "output_tokens": 20
        }),
        json.dumps({
            "ts": "2026-07-21T10:01:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "session_cumulative",
            "session_id": "sess-1", "turn_id": "t2", "input_tokens": 150, "output_tokens": 30
        }),
    ]), encoding="utf-8")

    res = diag.load_recent_session_consumption(cost_log)
    assert len(res) == 1
    # Latest snapshot should be used (150 and 30)
    assert res[0]["input_tokens"] == 150
    assert res[0]["output_tokens"] == 30
    assert res[0].get("token_coverage") != "partial"


def test_aggregation_mixed_scope_uses_turns_only_and_reports_partial(tmp_path):
    """Mixed turn + cumulative groups must use turn rows only and report token_coverage: 'partial'."""
    cost_log = tmp_path / "cost-log.jsonl"
    cost_log.write_text("\n".join([
        json.dumps({
            "ts": "2026-07-21T10:00:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t1", "input_tokens": 100, "output_tokens": 20
        }),
        json.dumps({
            "ts": "2026-07-21T10:01:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "session_cumulative",
            "session_id": "sess-1", "turn_id": "cumulative-1", "input_tokens": 150, "output_tokens": 30
        }),
    ]), encoding="utf-8")

    res = diag.load_recent_session_consumption(cost_log)
    assert len(res) == 1
    # Sum only the turn rows (input=100, output=20)
    assert res[0]["input_tokens"] == 100
    assert res[0]["output_tokens"] == 20
    assert res[0]["token_coverage"] == "partial"


def test_aggregation_invalid_tokens_rejected_or_marked_unknown(tmp_path):
    """Null, negative, or malformed tokens must be marked unknown/None, and negative/malformed values rejected."""
    cost_log = tmp_path / "cost-log.jsonl"
    cost_log.write_text("\n".join([
        # Null tokens (valid for unknown, kept as None)
        json.dumps({
            "ts": "2026-07-21T10:00:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t1", "input_tokens": None, "output_tokens": None
        }),
        # Negative tokens (invalid, must be ignored or skipped)
        json.dumps({
            "ts": "2026-07-21T10:01:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t2", "input_tokens": -50, "output_tokens": -10
        }),
        # Malformed tokens (invalid string, must be ignored or skipped)
        json.dumps({
            "ts": "2026-07-21T10:02:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t3", "input_tokens": "malformed", "output_tokens": {}
        }),
    ]), encoding="utf-8")

    res = diag.load_recent_session_consumption(cost_log)
    assert len(res) == 1
    assert res[0]["input_tokens"] is None
    assert res[0]["output_tokens"] is None


def test_aggregation_failed_but_metered_turns_count(tmp_path):
    """Failed turns (success=False) that still consumed tokens must be included in totals."""
    cost_log = tmp_path / "cost-log.jsonl"
    cost_log.write_text("\n".join([
        json.dumps({
            "ts": "2026-07-21T10:00:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t1", "input_tokens": 100, "output_tokens": 20, "success": True
        }),
        json.dumps({
            "ts": "2026-07-21T10:01:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t2", "input_tokens": 40, "output_tokens": 8, "success": False
        }),
    ]), encoding="utf-8")

    res = diag.load_recent_session_consumption(cost_log)
    assert len(res) == 1
    assert res[0]["input_tokens"] == 140
    assert res[0]["output_tokens"] == 28


def test_aggregation_cost_usd_summed_correctly(tmp_path):
    """cost_usd values must be summed correctly. If all are null, it must remain null."""
    cost_log = tmp_path / "cost-log.jsonl"
    cost_log.write_text("\n".join([
        json.dumps({
            "ts": "2026-07-21T10:00:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-cost", "turn_id": "t1", "input_tokens": 10, "output_tokens": 2, "cost_usd": 0.05
        }),
        json.dumps({
            "ts": "2026-07-21T10:01:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-cost", "turn_id": "t2", "input_tokens": 20, "output_tokens": 4, "cost_usd": None
        }),
        json.dumps({
            "ts": "2026-07-21T10:02:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-cost", "turn_id": "t3", "input_tokens": 30, "output_tokens": 6, "cost_usd": 0.10
        }),
    ]), encoding="utf-8")

    res = diag.load_recent_session_consumption(cost_log)
    assert len(res) == 1
    assert pytest.approx(res[0]["cost_usd"]) == 0.15


def test_aggregation_recency_ordering_and_deterministic_ties_and_limit(tmp_path):
    """Results must be ordered by last_ts descending, with deterministic tie-break, capped at limit (default 10)."""
    cost_log = tmp_path / "cost-log.jsonl"

    # Write 12 sessions
    lines = []
    for i in range(12):
        ts = f"2026-07-21T10:00:{i:02d}Z"
        lines.append(json.dumps({
            "ts": ts, "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": f"sess-{i}", "turn_id": "t1", "input_tokens": 10, "output_tokens": 2
        }))
    cost_log.write_text("\n".join(lines), encoding="utf-8")

    # 1. Test limit 10
    res = diag.load_recent_session_consumption(cost_log, limit=10)
    assert len(res) == 10
    # Capped at most recent 10 (sess-11 down to sess-2)
    assert [r["session_id"] for r in res] == [f"sess-{11 - j}" for j in range(10)]

    # 2. Test deterministic tie-break
    # Write same-timestamp rows for sess-a and sess-b
    cost_log.write_text("\n".join([
        json.dumps({
            "ts": "2026-07-21T12:00:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-b", "turn_id": "t1", "input_tokens": 10, "output_tokens": 2
        }),
        json.dumps({
            "ts": "2026-07-21T12:00:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-a", "turn_id": "t1", "input_tokens": 10, "output_tokens": 2
        }),
    ]), encoding="utf-8")

    res_tie = diag.load_recent_session_consumption(cost_log)
    # Alphabetical order: sess-a, then sess-b
    assert [r["session_id"] for r in res_tie[:2]] == ["sess-a", "sess-b"]


def test_aggregation_malformed_jsonl_lines_skipped_safely(tmp_path):
    """Malformed or invalid JSON lines must be safely skipped and not abort processing of valid rows."""
    cost_log = tmp_path / "cost-log.jsonl"
    cost_log.write_text("\n".join([
        json.dumps({
            "ts": "2026-07-21T10:00:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t1", "input_tokens": 100, "output_tokens": 20
        }),
        "INVALID_JSON_HERE{",
        "",  # Empty line
        json.dumps({
            "ts": "2026-07-21T10:01:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-1", "turn_id": "t2", "input_tokens": 50, "output_tokens": 10
        }),
    ]), encoding="utf-8")

    res = diag.load_recent_session_consumption(cost_log)
    assert len(res) == 1
    assert res[0]["input_tokens"] == 150


# ── 4. Exact Worked Example Test ──────────────────────────────────────────────

def test_worked_example_from_spec_section_3_4(tmp_path):
    """Verify exact worked-example numbers from §3.4:
    Turn T1: input=100 cached=80 output=20 reasoning=5 total=120
    Turn T2: input=40  cached=30 output=10 reasoning=3 total=50
    Cumulative after T2: input=140 output=30 total=170
    Total should sum turns only -> input=140, output=30, reasoning=8, total_tokens=170 (never 290).

    The cumulative snapshot row deliberately uses a DISTINCT turn_id
    ("cumulative-after-T2") from the real T2 turn row - reusing "T2" would
    collide under the (peer, session, turn_id) dedup key and silently
    discard the genuine T2 turn data before aggregation ever ran, which
    would defeat the point of this test (caught while reviewing this file
    before saving it).
    """
    cost_log = tmp_path / "cost-log.jsonl"
    cost_log.write_text("\n".join([
        # Turn T1
        json.dumps({
            "ts": "2026-07-21T10:00:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-example", "turn_id": "T1", "input_tokens": 100, "output_tokens": 20, "reasoning_tokens": 5
        }),
        # Turn T2
        json.dumps({
            "ts": "2026-07-21T10:01:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "turn",
            "session_id": "sess-example", "turn_id": "T2", "input_tokens": 40, "output_tokens": 10, "reasoning_tokens": 3
        }),
        # Cumulative after T2 - distinct turn_id, does not collide with T2's dedup key
        json.dumps({
            "ts": "2026-07-21T10:02:00Z", "peer_id": "cx", "model_id": "m", "token_scope": "session_cumulative",
            "session_id": "sess-example", "turn_id": "cumulative-after-T2", "input_tokens": 140, "output_tokens": 30
        }),
    ]), encoding="utf-8")

    res = diag.load_recent_session_consumption(cost_log)
    assert len(res) == 1
    session = res[0]

    # Sum only turn rows (T1 + T2):
    # input = 100 + 40 = 140
    # output = 20 + 10 = 30
    # reasoning = 5 + 3 = 8
    assert session["input_tokens"] == 140
    assert session["output_tokens"] == 30
    assert session["reasoning_tokens"] == 8
    assert session["total_tokens"] == 170  # (input_tokens + output_tokens)
    assert session["token_coverage"] == "partial"
