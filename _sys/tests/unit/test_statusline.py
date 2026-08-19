"""
Statusline Unification Tests — TDD for unified statusline architecture.

Validates:
1. Schema file exists and is well-formed
2. Unified script exists
3. All peer adapters exist and reference the unified script
4. infra.json registers all statusline paths
5. Codex config.toml follows unified field order
6. Hub status command still works
"""
import json
import subprocess
import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
SYS_DIR = ROOT / "_sys"
STATUSLINE_SCRIPT = SYS_DIR / "ai" / "common" / "statusline" / "statusline-unified.sh"
JQ_EXE = SYS_DIR / "tools" / "jq" / "jq.exe"


def _production_quota_filter():
    script = STATUSLINE_SCRIPT.read_text(encoding="utf-8")
    marker = "QUOTA_FILTER=$(cat <<'JQ'\n"
    assert marker in script
    return script.split(marker, 1)[1].split("\nJQ\n)", 1)[0]


def _render_quota_buckets(payload):
    result = subprocess.run(
        [str(JQ_EXE), "-r", _production_quota_filter()],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class TestStatuslineSchema:
    """Validate the unified statusline schema."""

    def test_schema_exists(self):
        schema_path = SYS_DIR / "ai" / "common" / "statusline" / "statusline-schema.json"
        assert schema_path.exists(), f"Missing: {schema_path}"

    def test_schema_valid_json(self):
        schema_path = SYS_DIR / "ai" / "common" / "statusline" / "statusline-schema.json"
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        assert "fields" in data
        assert "peer_mapping" in data
        assert "separator" in data

    def test_schema_v2_declares_canonical_repeated_quota_buckets(self):
        schema_path = SYS_DIR / "ai" / "common" / "statusline" / "statusline-schema.json"
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        quota = next(field for field in data["fields"] if field["id"] == "rate_limits")

        assert data["schema_version"] == 2
        assert quota["type"] == "repeated"
        assert quota["item_format"] == "{label}:{used_pct}%"
        assert quota["canonical_order"] == [
            "C-5H", "C-7D", "F-7D", "G-5H", "G-7D", "3P-5H", "3P-7D",
        ]
        assert quota["fallback"] == "quota:N/A"

    def test_schema_has_required_fields(self):
        schema_path = SYS_DIR / "ai" / "common" / "statusline" / "statusline-schema.json"
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        field_ids = [f["id"] for f in data["fields"]]
        assert "peer_model" in field_ids
        assert "context" in field_ids
        assert "location" in field_ids
        assert "rate_limits" in field_ids

    def test_schema_has_all_peers(self):
        schema_path = SYS_DIR / "ai" / "common" / "statusline" / "statusline-schema.json"
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        peers = data["peer_mapping"]
        assert "cc" in peers
        assert "ag" in peers
        assert "cx" in peers

    def test_schema_peer_mechanisms(self):
        schema_path = SYS_DIR / "ai" / "common" / "statusline" / "statusline-schema.json"
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        peers = data["peer_mapping"]
        assert peers["cc"]["mechanism"] == "command_script"
        assert peers["ag"]["mechanism"] == "command_script"
        assert peers["cx"]["mechanism"] == "builtin_enum"


class TestStatuslineScripts:
    """Validate that all statusline scripts exist."""

    def test_unified_script_exists(self):
        unified = SYS_DIR / "ai" / "common" / "statusline" / "statusline-unified.sh"
        assert unified.exists(), f"Missing unified script: {unified}"

    def test_cc_adapter_exists(self):
        cc = SYS_DIR / "claude" / "config" / "statusline-command.sh"
        assert cc.exists(), f"Missing cc adapter: {cc}"

    def test_ag_adapter_exists(self):
        ag = SYS_DIR / "antigravity" / "config" / "statusline-command.sh"
        assert ag.exists(), f"Missing ag adapter: {ag}"

    def test_cc_adapter_references_unified(self):
        cc = SYS_DIR / "claude" / "config" / "statusline-command.sh"
        content = cc.read_text(encoding="utf-8")
        assert "statusline-unified.sh" in content, "cc adapter must reference unified script"

    def test_ag_adapter_references_unified(self):
        ag = SYS_DIR / "antigravity" / "config" / "statusline-command.sh"
        content = ag.read_text(encoding="utf-8")
        assert "statusline-unified.sh" in content, "ag adapter must reference unified script"

    def test_cc_adapter_uses_peer_id_cc(self):
        cc = SYS_DIR / "claude" / "config" / "statusline-command.sh"
        content = cc.read_text(encoding="utf-8")
        assert '"cc"' in content, "cc adapter must pass peer_id 'cc'"

    def test_ag_adapter_uses_peer_id_ag(self):
        ag = SYS_DIR / "antigravity" / "config" / "statusline-command.sh"
        content = ag.read_text(encoding="utf-8")
        assert '"ag"' in content, "ag adapter must pass peer_id 'ag'"


class TestStatuslineQuotaBuckets:
    """T55: shape-driven, peer-agnostic quota presentation."""

    @staticmethod
    def _base(**extra):
        payload = {
            "model_name": "Fixture",
            "cwd": "C:/fixture",
            "context_used_tokens": 0,
            "context_total_tokens": 0,
        }
        payload.update(extra)
        return payload

    def test_cc_without_real_fable_bucket_omits_f7d(self):
        rendered = _render_quota_buckets(self._base(
            rate_5h_pct=105,
            rate_limits={"seven_day": {"used_percentage": 14}},
        ))

        assert rendered == "C-5H:105% C-7D:14%"
        assert "F-7D" not in rendered

    def test_cc_real_fable_weekly_bucket_is_rendered_in_canonical_order(self):
        rendered = _render_quota_buckets(self._base(rate_limits={
            "five_hour": {"used_percent": 10},
            "seven_day": 20,
            "fable_weekly_unusable": {"used_percentage": "unknown"},
            "FableSevenDay": {"used_percentage": 12},
        }))

        assert rendered == "C-5H:10% C-7D:20% F-7D:12%"

    def test_ag_renders_all_four_buckets_and_preserves_zero(self):
        rendered = _render_quota_buckets(self._base(quota={
            "gemini-5h": {"remaining_fraction": 1.0},
            "gemini-weekly": {"remaining_fraction": 0.58},
            "3p-5h": {"remaining_fraction": 1.0},
            "3p-weekly": {"remaining_fraction": 0.98},
        }))

        assert rendered == "G-5H:0% G-7D:42% 3P-5H:0% 3P-7D:2%"

    def test_invalid_shapes_are_skipped_and_valid_alias_fallback_wins(self):
        rendered = _render_quota_buckets(self._base(
            rate_5h_pct="garbage",
            rate_limits={"five_hour": {"used_percent": 7}},
            quota={
                "gemini-weekly": {"used_percentage": "not-a-number"},
                "3p-weekly": {"used_percent": 2},
            },
        ))

        assert rendered == "C-5H:7% 3P-7D:2%"

    def test_individually_missing_buckets_are_omitted(self):
        rendered = _render_quota_buckets(self._base(
            quota={"gemini-weekly": {"used_percentage": 33}},
        ))

        assert rendered == "G-7D:33%"

    def test_no_observed_bucket_uses_single_quota_na_fallback(self):
        rendered = _render_quota_buckets(self._base(
            rate_limits={"five_hour": {"used_percentage": "unknown"}},
            quota={"3p-5h": None},
        ))

        assert rendered == "quota:N/A"

    def test_quota_filter_is_peer_agnostic(self):
        assert "PEER_ID" not in _production_quota_filter()


class TestStatuslineConfig:
    """Validate peer configuration files reference statusline."""

    def test_cc_settings_has_statusline(self):
        settings = SYS_DIR / "claude" / "config" / "settings.json"
        data = json.loads(settings.read_text(encoding="utf-8"))
        assert "statusLine" in data
        assert data["statusLine"]["type"] == "command"

    def test_ag_settings_has_statusline(self):
        settings = SYS_DIR / "antigravity" / "config" / "settings.json"
        data = json.loads(settings.read_text(encoding="utf-8"))
        assert "statusLine" in data
        assert data["statusLine"]["type"] == "command"
        assert data["statusLine"].get("enabled") is True

    def test_cx_config_has_status_line(self):
        config = SYS_DIR / "codex" / "config" / "config.toml"
        content = config.read_text(encoding="utf-8")
        assert "status_line" in content
        assert "model-with-reasoning" in content

    def test_cx_field_order_model_first(self):
        """Codex status_line should start with model (unified order)."""
        config = SYS_DIR / "codex" / "config" / "config.toml"
        content = config.read_text(encoding="utf-8")
        # Find the status_line array
        for line in content.splitlines():
            if line.strip().startswith("status_line"):
                # model-with-reasoning should be first
                assert line.index("model-with-reasoning") > 0  # Should be in the line
                if "current-dir" in line:
                    model_pos = line.index("model-with-reasoning")
                    dir_pos = line.index("current-dir")
                    assert model_pos < dir_pos, "model must come before dir in unified order"
                break


class TestInfraRegistration:
    """Validate infra.json has all statusline paths registered."""

    def test_infra_cc_statusline(self):
        infra = json.loads((SYS_DIR / "ai" / "infra.json").read_text(encoding="utf-8"))
        assert "statusline" in infra["config_registry"]["cc"]

    def test_infra_ag_statusline(self):
        infra = json.loads((SYS_DIR / "ai" / "infra.json").read_text(encoding="utf-8"))
        assert "statusline" in infra["config_registry"]["ag"]

    def test_infra_cx_statusline(self):
        infra = json.loads((SYS_DIR / "ai" / "infra.json").read_text(encoding="utf-8"))
        assert "statusline_config" in infra["config_registry"]["cx"]

    def test_infra_common_unified(self):
        infra = json.loads((SYS_DIR / "ai" / "infra.json").read_text(encoding="utf-8"))
        assert "statusline_unified" in infra["config_registry"]["common"]
        assert "statusline_schema" in infra["config_registry"]["common"]

    def test_infra_statusline_paths_exist(self):
        """All registered statusline paths must point to real files."""
        infra = json.loads((SYS_DIR / "ai" / "infra.json").read_text(encoding="utf-8"))
        base = ROOT
        paths_to_check = [
            infra["config_registry"]["cc"]["statusline"],
            infra["config_registry"]["ag"]["statusline"],
            infra["config_registry"]["cx"]["statusline_config"],
            infra["config_registry"]["common"]["statusline_unified"],
            infra["config_registry"]["common"]["statusline_schema"],
        ]
        for rel_path in paths_to_check:
            full = base / rel_path
            assert full.exists(), f"Registered path missing: {rel_path} → {full}"


class TestStatuslineHubIntegration:
    """Validate the hub status command still works (regression)."""

    @pytest.fixture
    def test_env(self, tmp_path):
        ai_dir = tmp_path / ".ai"
        ai_dir.mkdir(exist_ok=True)
        venv_py = ROOT / "_sys" / "env" / "venv" / "Scripts" / "python.exe"
        hub_py = ROOT / "_sys" / "core" / "hub.py"
        return {"root": tmp_path, "venv_py": venv_py, "hub_py": hub_py}

