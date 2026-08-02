"""T88: warn on substantial asks with suspiciously short 3P-profile replies."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "_sys" / "core"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

import hub


def _substantial_context(warning_chars=300):
    return {
        "warning_chars": warning_chars,
        "substantial_reasons": ["task_items=6 > limit=5"],
        "task_count": 6,
        "query_chars": 1200,
        "max_tasks": 5,
        "max_chars": 8000,
    }


def test_warning_capability_is_scoped_to_affected_profiles():
    configured = {}
    for node in hub._load_orchestration().get("hub_nodes", []):
        root = node.get("node_id")
        for profile_name, profile in (node.get("profiles") or {}).items():
            threshold = profile.get("suspicious_short_reply_warning_chars")
            if threshold:
                configured[f"{root}.{profile_name}"] = threshold

    assert configured == {"ag.opus": 300, "ag.gptoss": 300}


def test_pending_success_warns_and_logs_before_normal_success(monkeypatch, tmp_path, capsys):
    events = []
    monkeypatch.setattr(hub, "_record_ask_success", lambda *a, **k: events.append("success"))
    monkeypatch.setattr(hub, "_append_ask_history", lambda *a, **k: None)
    monkeypatch.setattr(
        hub,
        "_record_routing_metric",
        lambda ai_root, event, **kw: events.append((event, kw)),
    )
    pending = hub._PendingAskSuccess(
        health_peer="ag",
        elapsed=279,
        ai_root=tmp_path,
        profile_key="opus",
        to="ag.opus",
        query_file=None,
        output_file=None,
        quiet=True,
        output="x" * 171,
        out_path=None,
        short_reply_warning_context=_substantial_context(),
    )

    pending.publish()

    err = capsys.readouterr().err
    assert "[HUB:WARN] ag.opus: suspiciously short reply" in err
    assert "automatic retry suppressed" in err
    assert events[0][0] == "suspicious_short_reply_detected"
    assert events[0][1]["reply_chars"] == 171
    assert events[0][1]["warning_chars"] == 300
    assert events[0][1]["automatic_retry"] is False
    assert events[1] == "success"


def test_warning_requires_both_substantial_signal_and_reply_below_threshold(capsys):
    assert not hub._warn_suspicious_short_reply(
        to="ag.opus", reply="x" * 171, ai_root=None, context=None
    )
    assert not hub._warn_suspicious_short_reply(
        to="ag.opus", reply="x" * 300, ai_root=None, context=_substantial_context()
    )
    assert "[HUB:WARN]" not in capsys.readouterr().err
