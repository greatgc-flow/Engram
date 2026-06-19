"""hub.py collaboration policies, feedback loop, and artifact workflow unit tests."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import hub


def _make_mock_proc(stdout=b"", stderr=b"", returncode=0):
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.returncode = returncode
    mock_proc.communicate.return_value = (stdout, stderr)
    mock_proc.poll.return_value = returncode
    mock_proc.stdout.read.return_value = stdout
    mock_proc.stderr.read.return_value = stderr
    return mock_proc

# 1. Test ask quiet mode and output file
def test_ask_quiet_and_output_file(ai_dir, tmp_path, capsys):
    # Setup node mock configuration
    nodes_cfg = {
        "version": "1",
        "nodes": {
            "mock_peer": {
                "invoke": "echo",
                "invoke_args": ["hello"],
                "requires_pty": False
            }
        }
    }
    (ai_dir / "nodes.json").write_text(json.dumps(nodes_cfg), encoding="utf-8")
    
    mock_proc = _make_mock_proc(stdout=b"mock output response")
    out_file = tmp_path / "ask_response.txt"

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("hub.is_routable", return_value=True):
        # Test output file with quiet=True
        hub.action_ask("mock_peer", "test query", None, 10, ai_dir, quiet=True, output_file=str(out_file))
        assert out_file.exists()
        assert out_file.read_text("utf-8") == "mock output response"

        captured = capsys.readouterr()
        assert "[HUB] REPLY" not in captured.out
        assert captured.out == ""

        # Test quiet=True without output file (should print raw output)
        hub.action_ask("mock_peer", "test query", None, 10, ai_dir, quiet=True, output_file=None)  # noqa: E501
        captured2 = capsys.readouterr()
        assert "[HUB] REPLY" not in captured2.out
        assert captured2.out == "mock output response"


def test_thin_forward_envelope_excludes_full_context(ai_dir):
    hub.action_init_session(ai_dir, "cx")
    state = json.loads((ai_dir / "state.json").read_text("utf-8"))
    session_dir = ai_dir / "sessions" / state["room_id"]
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "handoff.md").write_text("## [ACTIVE_THREADS]\n" + ("large context\n" * 200), encoding="utf-8")

    envelope = hub._thin_forward_envelope(ai_dir, "hello", "cx", "cx")

    assert "USER_QUERY:\nhello" in envelope
    assert "STATE_REFS:" in envelope
    assert "large context" not in envelope
    assert "HUB CONTEXT" not in envelope


def test_matching_peers_uses_scores(ai_dir):
    state = {
        "active_coordinator": "cx",
        "role_assignments": {},
    }
    (ai_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    health = {
        "cx": {
            "peer_id": "cx",
            "profile": {"tier": "mid", "cost_tier": "mid", "capabilities": ["focused-implementation"]},
            "context_health": {"status": "GREEN", "checked_at": "29990101T000000"},
            "session_health": {"session_count_today": 1},
            "availability": {"gate_open": True},
        },
        "cc": {
            "peer_id": "cc",
            "profile": {"tier": "mid", "cost_tier": "high", "capabilities": ["implementation"]},
            "context_health": {"status": "GREEN", "checked_at": "29990101T000000"},
            "session_health": {"session_count_today": 1},
            "availability": {"gate_open": True},
        },
    }
    with patch("hub.find_ai_root", return_value=ai_dir), \
         patch("hub._read_peer_health", side_effect=lambda peer: (ai_dir / f"{peer}.json", health[peer])), \
         patch("hub._load_orchestration", return_value={
             "hub_nodes": [
                 {"node_id": "cx", "aliases": [], "invoke": "mock"},
                 {"node_id": "cc", "aliases": [], "invoke": "mock"},
             ]
         }), \
         patch("hub._load_protocol_cfg", return_value={
             "leader_election": {
                 "election_score": {
                     "capability_match_max": 10,
                     "health_score": {"GREEN": 3, "YELLOW": 1, "STALE": -5, "RED": "blocked"},
                     "continuity_bonus_max": 2,
                     "console_fit_bonus_max": 1,
                     "cost_penalty": {"low": 0, "mid": 1, "high": 2},
                     "cold_start_penalty_max": 1,
                 }
             },
             "workload": {"capability_registry": {}}
         }):
        matches = hub._matching_peers("implementation")
    assert matches[0]["node_id"] == "cx"
    assert "score" in matches[0]


def test_task_checkpoint_writes_schema(ai_dir):
    state = {
        "role_assignments": {
            "implementer": {"peer": "cx", "status": "ACTIVE", "assigned_at": "now"}
        }
    }
    (ai_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    hub.action_task_checkpoint(ai_dir, "task-1", "cx", "checkpoint note")
    data = json.loads((ai_dir / "task_registry.json").read_text("utf-8"))
    task = data["task-1"]
    assert task["task_id"] == "task-1"
    assert task["owner"] == "cx"
    assert task["status"] == "ACTIVE"
    assert task["checkpoints"][0]["note"] == "checkpoint note"


def test_role_guard_blocks_wrong_role(ai_dir):
    state = {
        "role_assignments": {
            "reviewer": {"peer": "cc", "status": "ACTIVE", "assigned_at": "now"}
        }
    }
    (ai_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        hub.action_task_checkpoint(ai_dir, "task-1", "cc", "bad checkpoint")
    assert excinfo.value.code == 3


def test_context_fill_prints_parsed_handoff_lists(ai_dir, capsys):
    hub.action_init_session(ai_dir, "cx")
    capsys.readouterr()
    state = json.loads((ai_dir / "state.json").read_text("utf-8"))
    session_dir = ai_dir / "sessions" / state["room_id"]
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "handoff.md").write_text(
        "## [GOAL]\n- keep context compact\n\n## [ACTIVE_THREADS]\n- review round\n",
        encoding="utf-8",
    )

    hub.action_context_fill(ai_dir, ["GOAL", "ACTIVE_THREADS"])
    out = capsys.readouterr().out

    assert "## [GOAL]" in out
    assert "keep context compact" in out
    assert "## [ACTIVE_THREADS]" in out
    assert "review round" in out


# 2. Test collab_rate guard on mutating action
def test_collab_rate_guard(ai_dir, capsys):
    # Initialize a session first so room_id is set
    hub.action_init_session(ai_dir, "cc")
    capsys.readouterr()
    
    # 10 is the collab_rate in protocol.json. Let's write protocol.json to mock env.
    proto_cfg = {
        "collab_rate": {"current": 10},
        "operational_guard": {
            "enabled": True,
            "collab_rate_guard": {
                "enabled": True,
                "threshold": 10,
                "require_finalized_consensus": True,
                "exempt_actions": []
            },
            "mutating_hub_actions": ["update-status"]
        }
    }
    with patch("hub._load_protocol_cfg", return_value=proto_cfg):
        # 1. No finalized consensus round exists
        with pytest.raises(SystemExit) as excinfo:
            hub._guard_action(ai_dir, "update-status", force_tier0=False)
        assert excinfo.value.code == 3
        captured = capsys.readouterr()
        assert "requires finalized consensus at collab_rate 10" in captured.err

        # 2. Bypass with force_tier0=True
        hub._guard_action(ai_dir, "update-status", force_tier0=True) # should not raise
        
        # 3. Create a finalized consensus round
        hub.action_consensus_propose(ai_dir, "finalize-consensus", ["cc"], "cc")
        capsys.readouterr()
        # Find round ID from files
        consensus_files = list((ai_dir / "consensus").glob("*.json"))
        assert len(consensus_files) > 0
        round_id = consensus_files[0].stem
        
        # Vote and finalize
        hub.action_consensus_vote(ai_dir, round_id, "cc", "agree", "agreeing")
        capsys.readouterr()
        
        # Now guard should pass since a finalized consensus round exists
        hub._guard_action(ai_dir, "update-status", force_tier0=False) # should not raise


# 3. Test feedback actions
def test_feedback_workflow(ai_dir, capsys):
    proto_cfg = {
        "feedback_loop": {
            "storage_path": "collaboration_feedback.jsonl"
        }
    }
    with patch("hub._load_protocol_cfg", return_value=proto_cfg):
        # Add feedback
        hub.action_feedback_add(ai_dir, "gc", "protocol", "high", "Test gap description", "Evidence details here")
        
        # Verify stored file
        fb_file = ai_dir / "collaboration_feedback.jsonl"
        assert fb_file.exists()
        lines = fb_file.read_text("utf-8").splitlines()
        assert len(lines) == 1
        item = json.loads(lines[0])
        assert item["source_peer"] == "gc"
        assert item["category"] == "protocol"
        assert item["severity"] == "high"
        assert item["title"] == "Test gap description"
        assert item["detail"] == "Evidence details here"
        assert item["status"] == "open"
        feedback_id = item["id"]
        assert feedback_id.startswith("GAP-")
        
        # List feedback
        capsys.readouterr()
        hub.action_feedback_list(ai_dir)
        out = capsys.readouterr().out
        assert feedback_id in out
        assert "Test gap description" in out
        
        # Resolve feedback
        hub.action_feedback_resolve(ai_dir, feedback_id, status="accepted", owner="cc")
        lines = fb_file.read_text("utf-8").splitlines()
        item_updated = json.loads(lines[0])
        assert item_updated["status"] == "accepted"
        assert item_updated["owner"] == "cc"


# 4. Test artifact actions
def test_artifact_workflow(ai_dir, tmp_path, capsys):
    proto_cfg = {
        "artifact_workflow": {
            "storage_path": "artifact_metadata.json"
        }
    }
    with patch("hub._load_protocol_cfg", return_value=proto_cfg):
        artifact_name = "test_artifact.md"
        
        # Claim artifact
        hub.action_artifact_claim(ai_dir, artifact_name, "gc")
        
        art_file = ai_dir / "artifact_metadata.json"
        assert art_file.exists()
        art_data = json.loads(art_file.read_text("utf-8"))
        assert artifact_name in art_data
        assert art_data[artifact_name]["owner"] == "gc"
        assert art_data[artifact_name]["status"] == "claimed"
        
        # Register draft
        hub.action_artifact_status(ai_dir, artifact_name, register_peer="cc", draft_path="drafts/test_artifact.cc.md")
        art_data = json.loads(art_file.read_text("utf-8"))
        assert art_data[artifact_name]["status"] == "draft"
        assert art_data[artifact_name]["drafts"]["cc"] == "drafts/test_artifact.cc.md"
        
        # Finalize artifact
        dummy_file = tmp_path / "actual_artifact.md"
        dummy_file.write_text("artifact finalized content", encoding="utf-8")
        hub.action_artifact_finalize(ai_dir, artifact_name, str(dummy_file))
        
        art_data = json.loads(art_file.read_text("utf-8"))
        assert art_data[artifact_name]["status"] == "finalized"
        assert art_data[artifact_name]["hash"].startswith("sha256:")
