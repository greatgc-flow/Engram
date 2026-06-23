"""
API Contract Tests — Signature Snapshot Guards

Locks public hub.py API contracts so silent refactors are caught immediately.
Strategy: Contract-First — these tests define the interface, not behavior.
Any change to a guarded signature MUST be accompanied by updating this file.

Covers:
  1. hub.py core API signatures
  2. protocol.json structure
  3. active-lessons.jsonl schema
  4. tool-registry.json entrypoints
  5. peers.json structure
"""
import inspect
import json
from pathlib import Path
import pytest

SYS_DIR = Path(__file__).parent.parent.parent.resolve()  # _sys/

import sys
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))
import core.hub as hub


# ─────────────────────────────────────────────────────────────────────────────
# 1. hub.py Core API Signature Contracts
# ─────────────────────────────────────────────────────────────────────────────

class TestLeafCfgContract:
    """_lease_cfg() → (heartbeat_sec, lease_timeout_sec, zombie_timeout_sec)"""

    def test_returns_3_tuple(self):
        result = hub._lease_cfg()
        assert len(result) == 3, "_lease_cfg() contract: must return exactly 3 values"

    def test_all_ints(self):
        heartbeat, lease, zombie = hub._lease_cfg()
        assert isinstance(heartbeat, int), "heartbeat_sec must be int"
        assert isinstance(lease, int), "lease_timeout_sec must be int"
        assert isinstance(zombie, int), "zombie_timeout_sec must be int"

    def test_lease_at_least_1800(self):
        _, lease, _ = hub._lease_cfg()
        assert lease >= 1800, "lease_timeout_sec must be >= 1800 sec (30 min)"

    def test_zombie_at_least_double_heartbeat(self):
        heartbeat, _, zombie = hub._lease_cfg()
        assert zombie >= heartbeat * 2, "zombie_timeout must be >= 2× heartbeat"


class TestActionAskContract:
    """action_ask() parameter contract"""

    def test_required_params(self):
        sig = inspect.signature(hub.action_ask)
        params = list(sig.parameters.keys())
        required = ["to", "query", "query_file", "timeout_sec", "ai_root"]
        for r in required:
            assert r in params, f"action_ask() missing required param: {r}"

    def test_optional_defaults(self):
        sig = inspect.signature(hub.action_ask)
        p = sig.parameters
        assert p["quiet"].default is False
        assert p["output_file"].default is None
        assert p["include_context"].default is True
        assert p["session_policy"].default == "auto"
        assert p["explicit_scope"].default is None


class TestPeerStatusContract:
    """action_peer_status() parameter contract."""

    def test_optional_defaults(self):
        sig = inspect.signature(hub.action_peer_status)
        p = sig.parameters
        assert p["node_id"].default is None
        assert p["include_all"].default is False


class TestActionLessonContract:
    """lesson-* action signatures"""

    def test_lesson_broadcast_params(self):
        sig = inspect.signature(hub.action_lesson_broadcast)
        params = list(sig.parameters.keys())
        assert "ai_root" in params
        assert "lesson_id" in params
        assert "from_peer" in params

    def test_lessons_propose_params(self):
        sig = inspect.signature(hub.action_lessons_propose)
        params = list(sig.parameters.keys())
        required = ["ai_root", "title", "rule", "category"]
        for r in required:
            assert r in params, f"action_lessons_propose() missing: {r}"

    def test_lessons_activate_params(self):
        sig = inspect.signature(hub.action_lessons_activate)
        params = list(sig.parameters.keys())
        assert "ai_root" in params
        assert "lesson_id" in params

    def test_lesson_sweep_params(self):
        sig = inspect.signature(hub.action_lesson_sweep)
        p = sig.parameters
        assert "ai_root" in p
        assert p["min_triggers"].default == 3
        assert p["stale_days"].default == 14


class TestActionThreadContract:
    """thread-* action signatures"""

    def test_thread_new_params(self):
        sig = inspect.signature(hub.action_thread_new)
        params = list(sig.parameters.keys())
        required = ["ai_root", "topic", "from_peer"]
        for r in required:
            assert r in params, f"action_thread_new() missing: {r}"

    def test_thread_append_params(self):
        sig = inspect.signature(hub.action_thread_append)
        params = list(sig.parameters.keys())
        required = ["ai_root", "topic", "from_peer", "msg"]
        for r in required:
            assert r in params, f"action_thread_append() missing: {r}"


class TestActionProposalContract:
    """proposal-* action signatures"""

    def test_proposal_add_params(self):
        sig = inspect.signature(hub.action_proposal_add)
        params = list(sig.parameters.keys())
        required = ["ai_root", "subject", "from_peer"]
        for r in required:
            assert r in params, f"action_proposal_add() missing: {r}"

    def test_proposal_add_defaults(self):
        p = inspect.signature(hub.action_proposal_add).parameters
        assert p["impact"].default == "med"


class TestActionDirectiveContract:
    """directive-* action signatures"""

    def test_directive_add_params(self):
        sig = inspect.signature(hub.action_directive_add)
        p = sig.parameters
        assert "ai_root" in p
        assert "rule" in p
        assert "source_peer" in p
        assert p["ttl_hours"].default == 6
        assert p["clear_condition"].default == "manual"


# ─────────────────────────────────────────────────────────────────────────────
# 2. protocol.json Structure Contract
# ─────────────────────────────────────────────────────────────────────────────

class TestProtocolJsonContract:
    PROTOCOL_PATH = SYS_DIR / "ai" / "protocol.json"

    @pytest.fixture(scope="class")
    def proto(self):
        return json.loads(self.PROTOCOL_PATH.read_text(encoding="utf-8"))

    def test_file_exists(self):
        assert self.PROTOCOL_PATH.exists(), "protocol.json must exist at _sys/ai/protocol.json"

    def test_required_top_level_keys(self, proto):
        required = [
            "_version", "collab_rate", "health", "session",
            "consensus", "active_constraints", "runtime"
        ]
        for key in required:
            assert key in proto, f"protocol.json missing required key: {key}"

    def test_collab_rate_has_current(self, proto):
        cr = proto["collab_rate"]
        assert "current" in cr, "collab_rate must have 'current' field"
        assert isinstance(cr["current"], int), "collab_rate.current must be int"
        assert 0 <= cr["current"] <= 10, "collab_rate.current must be 0-10"

    def test_active_constraints_ipc_naming(self, proto):
        ac = proto.get("active_constraints", {})
        assert "ipc_query_file_naming" in ac, (
            "active_constraints must have ipc_query_file_naming"
        )

    def test_health_section_has_thresholds(self, proto):
        health = proto.get("health", {})
        assert "thresholds" in health, "health section must have 'thresholds'"

    def test_consensus_section_has_voters(self, proto):
        consensus = proto.get("consensus", {})
        assert "r10_voters" in consensus or "default_voters" in consensus, (
            "consensus section must have 'r10_voters' or 'default_voters'"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3. active-lessons.jsonl Schema Contract
# ─────────────────────────────────────────────────────────────────────────────

LESSONS_PATH = SYS_DIR / "ai" / "knowledge" / "general" / "active-lessons.jsonl"
REQUIRED_LESSON_KEYS = {
    "id", "schema_version", "status", "severity",
    "title", "compact_rule", "category", "scope",
    "applies_to", "source_refs", "approval", "retirement"
}
VALID_STATUSES = {"active", "proposed", "retired"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}


class TestActiveLessonsContract:

    @pytest.fixture(scope="class")
    def lessons(self):
        if not LESSONS_PATH.exists():
            return []
        lines = LESSONS_PATH.read_text(encoding="utf-8").splitlines()
        return [json.loads(ln) for ln in lines if ln.strip()]

    def test_file_exists(self):
        assert LESSONS_PATH.exists(), f"active-lessons.jsonl missing: {LESSONS_PATH}"

    def test_each_record_has_required_keys(self, lessons):
        for rec in lessons:
            missing = REQUIRED_LESSON_KEYS - rec.keys()
            assert not missing, f"Lesson {rec.get('id', '?')} missing keys: {missing}"

    def test_id_format(self, lessons):
        for rec in lessons:
            assert rec["id"].startswith("LL-"), (
                f"Lesson ID must start with 'LL-': {rec['id']}"
            )

    def test_status_values(self, lessons):
        for rec in lessons:
            assert rec["status"] in VALID_STATUSES, (
                f"Lesson {rec['id']} invalid status: {rec['status']}"
            )

    def test_severity_values(self, lessons):
        for rec in lessons:
            assert rec["severity"] in VALID_SEVERITIES, (
                f"Lesson {rec['id']} invalid severity: {rec['severity']}"
            )

    def test_applies_to_has_peer_ids(self, lessons):
        for rec in lessons:
            at = rec["applies_to"]
            assert isinstance(at, dict), (
                f"Lesson {rec['id']} applies_to must be a dict"
            )
            assert "peer_ids" in at, (
                f"Lesson {rec['id']} applies_to must contain 'peer_ids'"
            )

    def test_no_duplicate_ids(self, lessons):
        ids = [rec["id"] for rec in lessons]
        assert len(ids) == len(set(ids)), f"Duplicate lesson IDs found: {ids}"


# ─────────────────────────────────────────────────────────────────────────────
# 4. tool-registry.json Entrypoint Contract
# ─────────────────────────────────────────────────────────────────────────────

TOOL_REGISTRY_PATH = SYS_DIR / "ai" / "common" / "tool-registry.json"
REQUIRED_AGENTS = {
    "architect", "implementer", "researcher",
    "portability-auditor", "proposer", "risk-scanner",
    "verifier", "cross-reviewer", "lesson-extractor"
}
REQUIRED_SKILLS = {
    "consensus-vote", "context-fill", "health-check",
    "lesson-add", "reflect", "peer-propose"
}


class TestToolRegistryContract:

    @pytest.fixture(scope="class")
    def registry(self):
        return json.loads(TOOL_REGISTRY_PATH.read_text(encoding="utf-8"))

    def test_file_exists(self):
        assert TOOL_REGISTRY_PATH.exists(), "tool-registry.json must exist"

    def test_has_tools_key(self, registry):
        assert "tools" in registry, "tool-registry.json must have 'tools' key"

    def test_required_tool_keys(self, registry):
        for tool in registry["tools"]:
            for key in ("tool_id", "type", "version", "entrypoint"):
                assert key in tool, f"Tool {tool.get('tool_id', '?')} missing key: {key}"

    def test_all_required_agents_present(self, registry):
        ids = {t["tool_id"] for t in registry["tools"] if t.get("type") == "agent"}
        missing = REQUIRED_AGENTS - ids
        assert not missing, f"Missing required agents: {missing}"

    def test_all_required_skills_present(self, registry):
        ids = {t["tool_id"] for t in registry["tools"] if t.get("type") == "skill"}
        missing = REQUIRED_SKILLS - ids
        assert not missing, f"Missing required skills: {missing}"

    def test_entrypoints_exist(self, registry):
        base = SYS_DIR.parent  # PortableDev root
        missing = []
        for tool in registry["tools"]:
            ep = tool.get("entrypoint", "")
            if ep:
                p = base / ep
                if not p.exists():
                    missing.append(f"{tool['tool_id']} → {ep}")
        assert not missing, f"Missing entrypoint files:\n" + "\n".join(missing)

    def test_no_duplicate_tool_ids(self, registry):
        ids = [t["tool_id"] for t in registry["tools"]]
        assert len(ids) == len(set(ids)), f"Duplicate tool IDs: {ids}"


# ─────────────────────────────────────────────────────────────────────────────
# 5. peers.json Structure Contract
# ─────────────────────────────────────────────────────────────────────────────

PEERS_PATH = SYS_DIR / "ai" / "peers.json"
REQUIRED_PEERS = {"claude", "gemini", "codex", "antigravity"}
REQUIRED_PEER_KEYS = {"enabled", "description", "root_dir", "sys_subdir"}


class TestPeersJsonContract:

    @pytest.fixture(scope="class")
    def peers_data(self):
        return json.loads(PEERS_PATH.read_text(encoding="utf-8"))

    def test_file_exists(self):
        assert PEERS_PATH.exists(), "peers.json must exist at _sys/ai/peers.json"

    def test_has_peers_key(self, peers_data):
        assert "peers" in peers_data, "peers.json must have top-level 'peers' key"

    def test_required_peers_present(self, peers_data):
        peers = peers_data["peers"]
        missing = REQUIRED_PEERS - peers.keys()
        assert not missing, f"Missing required peers: {missing}"

    def test_each_peer_has_required_fields(self, peers_data):
        for peer_id, cfg in peers_data["peers"].items():
            for key in REQUIRED_PEER_KEYS:
                assert key in cfg, f"Peer '{peer_id}' missing required field: '{key}'"

    def test_each_peer_has_sys_subdir(self, peers_data):
        base = SYS_DIR.parent
        for peer_id, cfg in peers_data["peers"].items():
            subdir = cfg.get("sys_subdir", "")
            if subdir:
                p = SYS_DIR / subdir
                assert p.exists(), (
                    f"Peer '{peer_id}' sys_subdir not found: _sys/{subdir}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# 6. runtime-directives.jsonl Schema Contract
# ─────────────────────────────────────────────────────────────────────────────

DIRECTIVES_PATH = SYS_DIR / "ai" / "runtime-directives.jsonl"
REQUIRED_DIRECTIVE_KEYS = {"id", "rule", "source_peer", "effective", "status"}


class TestRuntimeDirectivesContract:

    @pytest.fixture(scope="class")
    def directives(self):
        if not DIRECTIVES_PATH.exists():
            return []
        lines = DIRECTIVES_PATH.read_text(encoding="utf-8").splitlines()
        return [json.loads(ln) for ln in lines if ln.strip()]

    def test_file_exists(self):
        assert DIRECTIVES_PATH.exists(), "runtime-directives.jsonl must exist"

    def test_each_record_has_required_keys(self, directives):
        for rec in directives:
            missing = REQUIRED_DIRECTIVE_KEYS - rec.keys()
            assert not missing, (
                f"Directive {rec.get('id', '?')} missing keys: {missing}"
            )

    def test_id_format(self, directives):
        for rec in directives:
            assert rec["id"].startswith("RD-"), (
                f"Directive ID must start with 'RD-': {rec['id']}"
            )

    def test_status_values(self, directives):
        valid = {"active", "resolved", "expired"}
        for rec in directives:
            assert rec["status"] in valid, (
                f"Directive {rec['id']} invalid status: {rec['status']}"
            )


class TestContextFillContract:
    """action_context_fill() parameter contract (DIR-003 / ARCH-07)."""
    def test_has_frame_param_default_false(self):
        sig = inspect.signature(hub.action_context_fill)
        assert "frame" in sig.parameters, "action_context_fill must expose frame param"
        assert sig.parameters["frame"].default is False, "frame must default False (cc/cx/gc unchanged)"
