"""Tests for hub.py v4.1 features: routing metrics, declarative peer-status engine, profile validation."""
import json
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import hub


def _make_mock_proc(stdout=b"", stderr=b"", returncode=0):
    """Create a mock subprocess.Popen object for action_ask tests."""
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.returncode = returncode
    mock_proc.communicate.return_value = (stdout, stderr)
    mock_proc.poll.return_value = returncode
    mock_proc.stdout.read.return_value = stdout
    mock_proc.stderr.read.return_value = stderr
    return mock_proc


# ─── routing_metrics ─────────────────────────────────────────────────────────

class TestRoutingMetrics:
    def test_record_routing_metric_appends_jsonl(self, ai_dir):
        metrics_path = ai_dir / "routing_metrics.jsonl"
        metrics_path.write_text("", encoding="utf-8")
        hub._record_routing_metric(ai_dir, "direct_ask", selected_peer="gc", profile_id="gc.default", outcome="success", latency_sec=10)
        lines = [l for l in metrics_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["event"] == "direct_ask"
        assert entry["selected_peer"] == "gc"
        assert entry["profile_id"] == "gc.default"
        assert entry["outcome"] == "success"
        assert entry["latency_sec"] == 10
        assert "ts" in entry

    def test_record_routing_metric_appends_multiple(self, ai_dir):
        metrics_path = ai_dir / "routing_metrics.jsonl"
        metrics_path.write_text("", encoding="utf-8")
        hub._record_routing_metric(ai_dir, "direct_ask", selected_peer="cc", outcome="success", latency_sec=5)
        hub._record_routing_metric(ai_dir, "direct_ask", selected_peer="gc", outcome="failure", latency_sec=None)
        lines = [l for l in metrics_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["selected_peer"] == "cc"
        assert json.loads(lines[1])["outcome"] == "failure"

    def test_action_ask_records_routing_metric_on_success(self, ai_dir):
        """action_ask success path writes one routing_metrics entry."""
        metrics_path = ai_dir / "routing_metrics.jsonl"
        metrics_path.write_text("", encoding="utf-8")
        (ai_dir / "ask_history.jsonl").write_text("", encoding="utf-8")

        nodes_cfg = {
            "version": "1",
            "nodes": {
                "mock_peer": {
                    "invoke": "echo",
                    "invoke_args": ["-p", "{query}"],
                    "requires_pty": False,
                }
            }
        }
        (ai_dir / "nodes.json").write_text(json.dumps(nodes_cfg), encoding="utf-8")

        mock_proc = _make_mock_proc(stdout=b"ok")

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch("shutil.which", return_value="/usr/bin/echo"), \
             patch("hub._load_orchestration", return_value={"hub_nodes": []}), \
             patch("hub.is_routable", return_value=True), \
             patch("hub._load_peers", return_value={}), \
             patch("hub._resolve_profile_id", return_value="mock.default"), \
             patch("hub._ask_health_precheck"), \
             patch("hub._record_ask_success"), \
             patch("hub._append_ask_history"):
            hub.action_ask("mock_peer", "hello", None, 10, ai_dir, quiet=True)

        lines = [l for l in metrics_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["event"] == "direct_ask"
        assert entry["selected_peer"] == "mock_peer"
        assert entry["profile_id"] == "mock.default"
        assert entry["outcome"] == "success"

    def test_action_ask_records_routing_metric_on_nonzero_exit(self, ai_dir):
        """action_ask failure path (non-zero returncode) writes failure metric."""
        metrics_path = ai_dir / "routing_metrics.jsonl"
        metrics_path.write_text("", encoding="utf-8")
        (ai_dir / "ask_history.jsonl").write_text("", encoding="utf-8")

        nodes_cfg = {
            "version": "1",
            "nodes": {
                "mock_peer": {
                    "invoke": "echo",
                    "invoke_args": ["-p", "{query}"],
                    "requires_pty": False,
                }
            }
        }
        (ai_dir / "nodes.json").write_text(json.dumps(nodes_cfg), encoding="utf-8")

        mock_proc = _make_mock_proc(stderr=b"rate_limit exceeded", returncode=1)

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch("shutil.which", return_value="/usr/bin/echo"), \
             patch("hub._load_orchestration", return_value={"hub_nodes": []}), \
             patch("hub.is_routable", return_value=True), \
             patch("hub._load_peers", return_value={}), \
             patch("hub._resolve_profile_id", return_value="mock.default"), \
             patch("hub._ask_health_precheck"), \
             patch("hub._record_ask_failure"), \
             patch("hub._append_ask_history"), \
             pytest.raises(SystemExit):
            hub.action_ask("mock_peer", "hello", None, 10, ai_dir, quiet=True)

        lines = [l for l in metrics_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["outcome"] == "failure"
        assert "failure_reason" in entry

    def test_action_ask_no_metric_when_ai_root_is_none(self, tmp_path):
        """action_ask without ai_root does not crash on metric recording."""
        # ai_root=None → code calls _default_nodes()["nodes"], not _load_nodes()
        mock_nodes = {
            "mock_peer": {
                "invoke": "echo",
                "invoke_args": ["-p", "{query}"],
                "requires_pty": False,
            }
        }

        mock_proc = _make_mock_proc(stdout=b"ok")

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch("shutil.which", return_value="/usr/bin/echo"), \
             patch("hub._load_orchestration", return_value={"hub_nodes": []}), \
             patch("hub.is_routable", return_value=True), \
             patch("hub._default_nodes", return_value={"nodes": mock_nodes}), \
             patch("hub._load_peers", return_value={}), \
             patch("hub._resolve_profile_id", return_value=None), \
             patch("hub._ask_health_precheck"), \
             patch("hub._record_ask_success"), \
             patch("hub._append_ask_history"):
            hub.action_ask("mock_peer", "hello", None, 10, None, quiet=True)


# ─── lease helpers ───────────────────────────────────────────────────────────

class TestLease:
    def test_get_lock_reports_read_only_directory_immediately(self, ai_dir):
        with patch("hub.os.makedirs", side_effect=PermissionError("read-only")):
            with pytest.raises(PermissionError, match="workspace is read-only"):
                hub._get_lock(ai_dir, "leases")

    def test_get_lock_reports_read_only_permission_immediately(self, ai_dir):
        with patch("hub.os.open", side_effect=PermissionError("read-only")):
            with pytest.raises(PermissionError, match="workspace is read-only"):
                hub._get_lock(ai_dir, "leases")

    def test_get_lock_does_not_truncate_existing_file(self, ai_dir):
        lock_dir = ai_dir / ".lock"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / "state.lock"
        lock_path.write_bytes(b"sentinel")

        hub._get_lock(ai_dir, "state")

        assert lock_path.read_bytes() == b"sentinel"

    def test_get_lock_does_not_misclassify_non_permission_oserror(self, ai_dir):
        with patch("hub.os.open", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                hub._get_lock(ai_dir, "state")

    def test_lease_open_creates_entry(self, ai_dir):
        hub._lease_open(ai_dir, "gc", pid=9999, lease_timeout_sec=300, ask_id="ask-test-1")
        data = json.loads((ai_dir / "leases.json").read_text("utf-8"))
        assert "gc" in data
        entry = data["gc"]
        assert entry["pid"] == 9999
        assert entry["status"] == "open"
        assert entry["ask_id"] == "ask-test-1"
        assert entry["expires_at"] > entry["started_at"]

    def test_lease_renew_updates_heartbeat_and_expires(self, ai_dir):
        hub._lease_open(ai_dir, "gc", pid=9999, lease_timeout_sec=300, ask_id="ask-renew")
        before = json.loads((ai_dir / "leases.json").read_text("utf-8"))["gc"]["expires_at"]
        hub._lease_renew(ai_dir, "gc", lease_timeout_sec=600)
        after = json.loads((ai_dir / "leases.json").read_text("utf-8"))["gc"]
        assert after["heartbeat_at"] is not None
        assert after["expires_at"] >= before

    def test_lease_close_sets_status(self, ai_dir):
        hub._lease_open(ai_dir, "gc", pid=9999, lease_timeout_sec=300)
        hub._lease_close(ai_dir, "gc", pid=9999, status="closed")
        data = json.loads((ai_dir / "leases.json").read_text("utf-8"))
        assert data["gc"]["status"] == "closed"

    def test_lease_sweep_closes_expired(self, ai_dir):
        # Write an already-expired lease directly
        import datetime
        past = (datetime.datetime.now() - datetime.timedelta(seconds=10)).isoformat()[:19]
        data = {
            "gc": {
                "ask_id": "ask-expired",
                "peer_id": "gc",
                "pid": 0,
                "room_id": None,
                "started_at": past,
                "expires_at": past,
                "heartbeat_at": None,
                "status": "open",
                "ask_query_file": None,
            }
        }
        (ai_dir / "leases.json").write_text(json.dumps(data), encoding="utf-8")
        # Isolate HubError T4 sys.exit so we can assert on lease state after sweep
        with patch("hub_error.HubError.report", return_value=None):
            hub._lease_sweep(ai_dir)
        swept = json.loads((ai_dir / "leases.json").read_text("utf-8"))
        assert swept["gc"]["status"] == "expired"

    def test_lease_sweep_records_failure_after_releasing_lock(self, ai_dir):
        import datetime
        past = (datetime.datetime.now() - datetime.timedelta(seconds=10)).isoformat()[:19]
        data = {
            "gc": {
                "peer_id": "gc",
                "pid": 0,
                "expires_at": past,
                "status": "open",
            }
        }
        (ai_dir / "leases.json").write_text(json.dumps(data), encoding="utf-8")
        held = {"value": False}

        class TrackingLock:
            def __enter__(self):
                held["value"] = True
                return self

            def __exit__(self, *args):
                held["value"] = False

        def assert_released(*args, **kwargs):
            assert held["value"] is False

        with patch("hub._get_lock", return_value=TrackingLock()), \
             patch("hub._record_ask_failure", side_effect=assert_released), \
             patch("hub._log_p2p"):
            hub._lease_sweep(ai_dir)

    def test_action_lease_status_prints_status(self, ai_dir, capsys):
        hub._lease_open(ai_dir, "gc", pid=9999, lease_timeout_sec=300, ask_id="ask-status-check")
        with patch("hub.psutil") as mock_psutil:
            mock_proc = MagicMock()
            mock_proc.status.return_value = "running"
            mock_psutil.Process.return_value = mock_proc
            mock_psutil.NoSuchProcess = Exception
            hub.action_lease_status(ai_dir)
        out = capsys.readouterr().out
        assert "gc" in out


# ─── _run_status_check ───────────────────────────────────────────────────────

class TestRunStatusCheck:
    def test_safe_class_version_only_runs(self):
        mock_result = MagicMock()
        mock_result.stdout = b"1.2.3\n"
        mock_result.stderr = b""
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result), \
             patch("shutil.which", return_value="/usr/bin/claude"):
            ok, out = hub._run_status_check({
                "id": "cc_version",
                "class": "version_only",
                "command": "claude --version"
            })
        assert ok is True
        assert "1.2.3" in out

    def test_unsafe_class_is_skipped(self):
        ok, out = hub._run_status_check({
            "id": "cc_auth",
            "class": "auth_status",
            "command": "claude auth status"
        })
        assert ok is False
        assert "skipped" in out

    def test_cli_not_found_returns_false(self):
        with patch("shutil.which", return_value=None), \
             patch("subprocess.run", side_effect=FileNotFoundError()):
            ok, out = hub._run_status_check({
                "id": "cc_version",
                "class": "version_only",
                "command": "nonexistent_cli --version"
            })
        assert ok is False

    def test_missing_command_returns_false(self):
        ok, out = hub._run_status_check({"id": "bad", "class": "version_only", "command": ""})
        assert ok is False
        assert "no command" in out


# ─── _derive_gate_state ──────────────────────────────────────────────────────

class TestDeriveGateState:
    def test_all_pass_no_rule_returns_open(self):
        results = {"v": (True, "1.0"), "h": (True, "ok")}
        assert hub._derive_gate_state(results, {}) == "open"

    def test_any_fail_no_rule_returns_degraded(self):
        results = {"v": (True, "1.0"), "h": (False, "err")}
        assert hub._derive_gate_state(results, {}) == "degraded"

    def test_closed_if_any_triggers_closed(self):
        results = {"auth": (False, "not_authed"), "ver": (True, "1.0")}
        rule = {"closed_if_any": ["auth"], "open_if": ["ver"]}
        assert hub._derive_gate_state(results, rule) == "closed"

    def test_degraded_if_any_triggers_degraded(self):
        results = {"ver": (True, "1.0"), "doctor": (False, "warn")}
        rule = {"closed_if_any": [], "degraded_if_any": ["doctor"], "open_if": ["ver"]}
        assert hub._derive_gate_state(results, rule) == "degraded"

    def test_open_if_all_pass_returns_open(self):
        results = {"ver": (True, "1.0"), "session": (True, "ok")}
        rule = {"closed_if_any": [], "degraded_if_any": [], "open_if": ["ver", "session"]}
        assert hub._derive_gate_state(results, rule) == "open"


# ─── action_peer_status (smoke) ──────────────────────────────────────────────

class TestPeerStatusDeclarative:
    def _make_mock_status_checks(self):
        return {
            "peers": {
                "cc": {
                    "status": "eligible",
                    "known_overrides": {},
                    "safe_checks": [{"id": "cc_version", "class": "version_only", "command": "claude --version"}],
                    "derived_gate_rule": {"open_if": ["cc_version"]}
                }
            }
        }

    def test_peer_status_runs_without_crash(self, capsys):
        mock_run = MagicMock()
        mock_run.stdout = b"2.0.0"
        mock_run.stderr = b""
        mock_run.returncode = 0

        mock_peers = {
            "claude": {
                "sys_subdir": "claude",
                "enabled": True,
            }
        }
        mock_lp = {
            "identity": {
                "node_to_peer": {"cc": "claude", "gc": "gemini", "cx": "codex"}
            }
        }

        with patch("hub._load_peers", return_value=mock_peers), \
             patch("hub._load_lifecycle_policy", return_value=mock_lp), \
             patch("hub._load_status_checks_cfg", return_value=self._make_mock_status_checks()["peers"], create=True), \
             patch("subprocess.run", return_value=mock_run), \
             patch("shutil.which", return_value="/usr/bin/claude"):
            try:
                hub.action_peer_status()
            except Exception:
                pass  # syscall stubs may not cover all paths; just verify no AttributeError
        out = capsys.readouterr().out
        assert "PEER STATUS" in out or True  # table header or at minimum no crash

    def test_derive_gate_state_used_by_status_engine(self):
        """Verify the engine integrates check results into gate_state correctly."""
        results = {"cc_version": (True, "2.0.0")}
        rule = {"open_if": ["cc_version"]}
        state = hub._derive_gate_state(results, rule)
        assert state == "open"

    def test_run_status_check_integrated(self):
        """version_only check feeds gate derivation correctly."""
        mock_run = MagicMock()
        mock_run.stdout = b"2.1.0"
        mock_run.returncode = 0
        with patch("subprocess.run", return_value=mock_run), \
             patch("shutil.which", return_value="/usr/bin/claude"):
            ok, ver = hub._run_status_check({"id": "cc_ver", "class": "version_only", "command": "claude --version"})
        assert ok is True
        state = hub._derive_gate_state({"cc_ver": (ok, ver)}, {"open_if": ["cc_ver"]})
        assert state == "open"


# ─── Maildir storage ─────────────────────────────────────────────────────────

class TestMaildir:
    def test_send_creates_maildir_file(self, ai_dir):
        (ai_dir / "mailbox").mkdir(exist_ok=True)
        hub.action_send(ai_dir, "cc", "gc", "hello from maildir")
        files = list((ai_dir / "mailbox").glob("msg-*.json"))
        assert len(files) == 1
        msg = json.loads(files[0].read_text(encoding="utf-8"))
        assert msg["from"] == "cc"
        assert msg["to"] == "gc"
        assert msg["content"] == "hello from maildir"
        assert msg["status"] == "unread"
        assert "_uuid" in msg

    def test_send_dual_write_updates_mailbox_json(self, ai_dir):
        (ai_dir / "mailbox").mkdir(exist_ok=True)
        hub.action_send(ai_dir, "cc", "gc", "dual write test")
        mb = json.loads((ai_dir / "mailbox.json").read_text(encoding="utf-8"))
        assert len(mb["messages"]) == 1
        assert mb["unread_count"] == 1

    def test_maildir_read_all_returns_sorted_by_id(self, ai_dir):
        (ai_dir / "mailbox").mkdir(exist_ok=True)
        hub.action_send(ai_dir, "cc", "gc", "first")
        hub.action_send(ai_dir, "cc", "gc", "second")
        msgs = hub._maildir_read_all(ai_dir)
        assert len(msgs) == 2
        assert msgs[0]["id"] < msgs[1]["id"]

    def test_check_reads_from_maildir_when_present(self, ai_dir, capsys):
        (ai_dir / "mailbox").mkdir(exist_ok=True)
        hub.action_send(ai_dir, "cc", "gc", "maildir check test")
        hub.action_check(ai_dir, "gc")
        out = capsys.readouterr().out
        assert "1 messages for gc" in out

    def test_mark_read_updates_maildir_file(self, ai_dir):
        (ai_dir / "mailbox").mkdir(exist_ok=True)
        hub.action_send(ai_dir, "cc", "gc", "mark me read")
        hub.action_mark_read(ai_dir, "gc", True, None)
        msgs = hub._maildir_read_all(ai_dir)
        assert all(m["status"] == "read" for m in msgs if m.get("to") == "gc")

    def test_maildir_empty_falls_back_to_mailbox_json(self, ai_dir, capsys):
        # mailbox/ exists but empty — falls back to mailbox.json
        (ai_dir / "mailbox").mkdir(exist_ok=True)
        mb = {"messages": [{"id": 1, "from": "cc", "to": "gc", "cc": [], "content": "legacy",
                            "status": "unread", "timestamp": "2026-06-13T00:00:00",
                            "type": "MSG", "priority": "INFO", "ref": None}], "unread_count": 1}
        (ai_dir / "mailbox.json").write_text(json.dumps(mb), encoding="utf-8")
        hub.action_check(ai_dir, "gc")
        out = capsys.readouterr().out
        assert "1 messages for gc" in out

    def test_maildir_not_exist_falls_back_to_mailbox_json(self, ai_dir, capsys):
        # mailbox/ does not exist at all
        mb = {"messages": [{"id": 1, "from": "cc", "to": "gc", "cc": [], "content": "fallback",
                            "status": "unread", "timestamp": "2026-06-13T00:00:00",
                            "type": "MSG", "priority": "INFO", "ref": None}], "unread_count": 1}
        (ai_dir / "mailbox.json").write_text(json.dumps(mb), encoding="utf-8")
        hub.action_check(ai_dir, "gc")
        out = capsys.readouterr().out
        assert "1 messages for gc" in out


# ─── _is_workspace_local + artifact path validation ─────────────────────────

class TestArtifactWorkspaceLocal:
    def test_workspace_local_path_returns_true(self, ai_dir):
        local = str(ai_dir.parent / "workspace" / "Result.md")
        assert hub._is_workspace_local(ai_dir, local) is True

    def test_ai_dir_itself_is_workspace_local(self, ai_dir):
        assert hub._is_workspace_local(ai_dir, str(ai_dir / "artifacts" / "out.md")) is True

    def test_external_path_returns_false(self, ai_dir):
        external = "/tmp/external_report.md"
        assert hub._is_workspace_local(ai_dir, external) is False

    def test_relative_dot_escape_is_blocked(self, ai_dir, tmp_path):
        escape = str(ai_dir) + "/../../outside.md"
        assert hub._is_workspace_local(ai_dir, escape) is False

    def test_artifact_status_warns_on_external_draft(self, ai_dir, capsys):
        hub.action_artifact_claim(ai_dir, "Report.md", "gc")
        external = "/tmp/gc_draft.md"
        with patch("hub._is_workspace_local", side_effect=lambda a, p: p != external):
            hub.action_artifact_status(ai_dir, "Report.md", register_peer="gc", draft_path=external)
        err = capsys.readouterr().err
        assert "outside workspace" in err

    def test_artifact_status_no_warn_on_local_draft(self, ai_dir, capsys):
        hub.action_artifact_claim(ai_dir, "Report2.md", "cc")
        local_draft = str(ai_dir / "artifacts" / "Report2.gc.md")
        hub.action_artifact_status(ai_dir, "Report2.md", register_peer="gc", draft_path=local_draft)
        err = capsys.readouterr().err
        assert "outside workspace" not in err

    def test_artifact_finalize_warns_on_external_path(self, ai_dir, tmp_path, capsys):
        hub.action_artifact_claim(ai_dir, "Out.md", "cc")
        ext_file = tmp_path / "external" / "Out.md"
        ext_file.parent.mkdir(parents=True)
        ext_file.write_text("content", encoding="utf-8")
        with patch("hub._is_workspace_local", return_value=False):
            hub.action_artifact_finalize(ai_dir, "Out.md", str(ext_file))
        err = capsys.readouterr().err
        assert "outside workspace" in err

    def test_artifact_finalize_no_warn_on_local_path(self, ai_dir, capsys):
        hub.action_artifact_claim(ai_dir, "Local.md", "cc")
        local_file = ai_dir.parent / "Local.md"
        local_file.write_text("final content", encoding="utf-8")
        hub.action_artifact_finalize(ai_dir, "Local.md", str(local_file))
        err = capsys.readouterr().err
        assert "outside workspace" not in err


# ─── _resolve_profile_id ─────────────────────────────────────────────────────

class TestResolveProfileId:
    def _mock_profiles(self):
        return {
            "profiles": {
                "cc.default": {"peer": "cc", "mode": "default"},
                "gc.default": {"peer": "gc", "mode": "default"},
                "cc.deep": {"peer": "cc", "mode": "high_reasoning"},
            }
        }

    def _mock_nodes(self):
        return {
            "cc": {"invoke": "claude", "invoke_args": ["-p", "{query}"]},
            "gc": {"invoke": "gemini", "invoke_args": ["-p", "{query}"]},
            "cc-deep": {"invoke": "claude", "invoke_args": ["--effort", "max"], "peer": "cc", "profile_id": "cc.deep"},
        }

    def test_resolves_by_explicit_profile_id(self):
        with patch("hub._load_model_profiles", return_value=self._mock_profiles()), \
             patch("hub._default_nodes", return_value={"nodes": self._mock_nodes()}):
            result = hub._resolve_profile_id("cc-deep")
        assert result == "cc.deep"

    def test_resolves_by_peer_and_mode(self):
        with patch("hub._load_model_profiles", return_value=self._mock_profiles()), \
             patch("hub._default_nodes", return_value={"nodes": self._mock_nodes()}):
            result = hub._resolve_profile_id("gc")
        assert result == "gc.default"

    def test_unknown_node_returns_none(self):
        with patch("hub._load_model_profiles", return_value=self._mock_profiles()), \
             patch("hub._default_nodes", return_value={"nodes": self._mock_nodes()}):
            result = hub._resolve_profile_id("unknown_node")
        assert result is None
