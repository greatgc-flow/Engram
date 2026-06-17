"""TDD — I2: peers.json model_profiles per-peer model selection.

Tests are written BEFORE model_profiles is added to peers.json.
All tests MUST FAIL until implementation is complete.
"""
import json
import pytest
from pathlib import Path

PEERS_JSON = Path(__file__).parent.parent.parent / "ai" / "peers.json"
ENABLED_PEERS = ("claude", "gemini", "codex")
REQUIRED_TIERS = ("standard", "effort", "deepthink")


# ── Schema presence ──────────────────────────────────────────────────────────

class TestModelProfilesSchema:
    def test_peers_json_exists(self):
        assert PEERS_JSON.exists(), "peers.json not found"

    def test_all_enabled_peers_have_model_profiles(self):
        data = json.loads(PEERS_JSON.read_text(encoding="utf-8"))
        peers = data.get("peers", {})
        missing = []
        for peer_id in ENABLED_PEERS:
            if peer_id not in peers:
                missing.append(f"{peer_id} (peer missing)")
            elif "model_profiles" not in peers[peer_id]:
                missing.append(f"{peer_id} (model_profiles missing)")
        assert not missing, f"Missing model_profiles: {missing}"

    def test_model_profiles_has_all_tiers(self):
        data = json.loads(PEERS_JSON.read_text(encoding="utf-8"))
        peers = data.get("peers", {})
        errors = []
        for peer_id in ENABLED_PEERS:
            if peer_id not in peers:
                continue
            profiles = peers[peer_id].get("model_profiles", {})
            for tier in REQUIRED_TIERS:
                if tier not in profiles:
                    errors.append(f"{peer_id}.model_profiles.{tier} missing")
        assert not errors, f"Missing tiers: {errors}"

    def test_no_null_model_values(self):
        data = json.loads(PEERS_JSON.read_text(encoding="utf-8"))
        peers = data.get("peers", {})
        nulls = []
        for peer_id in ENABLED_PEERS:
            if peer_id not in peers:
                continue
            profiles = peers[peer_id].get("model_profiles", {})
            for tier, model in profiles.items():
                if not model:
                    nulls.append(f"{peer_id}.{tier}={model!r}")
        assert not nulls, f"Null/empty model values: {nulls}"

    def test_model_values_are_strings(self):
        data = json.loads(PEERS_JSON.read_text(encoding="utf-8"))
        peers = data.get("peers", {})
        non_strings = []
        for peer_id in ENABLED_PEERS:
            if peer_id not in peers:
                continue
            profiles = peers[peer_id].get("model_profiles", {})
            for tier, model in profiles.items():
                if not isinstance(model, str):
                    non_strings.append(f"{peer_id}.{tier}={model!r}")
        assert not non_strings, f"Non-string model values: {non_strings}"

    def test_tier_keys_are_standardized(self):
        """All peers must use the same tier key names (no aliases)."""
        data = json.loads(PEERS_JSON.read_text(encoding="utf-8"))
        peers = data.get("peers", {})
        for peer_id in ENABLED_PEERS:
            if peer_id not in peers:
                continue
            profiles = peers[peer_id].get("model_profiles", {})
            extra = set(profiles.keys()) - set(REQUIRED_TIERS)
            # Extra tiers are allowed, but must not REPLACE required ones
            for req in REQUIRED_TIERS:
                assert req in profiles, f"{peer_id} missing required tier '{req}'"


# ── Content validation ───────────────────────────────────────────────────────

class TestModelProfilesContent:
    def test_claude_standard_is_haiku_class(self):
        """claude standard should be a haiku/flash class model (cheap/fast)."""
        data = json.loads(PEERS_JSON.read_text(encoding="utf-8"))
        model = data["peers"]["claude"]["model_profiles"]["standard"]
        assert "haiku" in model.lower() or "flash" in model.lower() or "mini" in model.lower(), \
            f"claude standard should be a fast/cheap model, got: {model}"

    def test_claude_deepthink_is_opus_class(self):
        """claude deepthink should be an opus/pro class model."""
        data = json.loads(PEERS_JSON.read_text(encoding="utf-8"))
        model = data["peers"]["claude"]["model_profiles"]["deepthink"]
        assert "opus" in model.lower() or "pro" in model.lower() or "sonnet" in model.lower(), \
            f"claude deepthink should be a capable model, got: {model}"

    def test_gemini_has_flash_for_standard(self):
        data = json.loads(PEERS_JSON.read_text(encoding="utf-8"))
        model = data["peers"]["gemini"]["model_profiles"]["standard"]
        assert "flash" in model.lower() or "mini" in model.lower() or "haiku" in model.lower(), \
            f"gemini standard should be flash class, got: {model}"

    def test_deepthink_more_capable_than_standard(self):
        """deepthink model name should differ from standard (not same model)."""
        data = json.loads(PEERS_JSON.read_text(encoding="utf-8"))
        peers = data.get("peers", {})
        for peer_id in ENABLED_PEERS:
            if peer_id not in peers:
                continue
            profiles = peers[peer_id].get("model_profiles", {})
            if "standard" in profiles and "deepthink" in profiles:
                # At minimum they should not be identical
                # (same model for effort vs deepthink is OK as fallback)
                assert profiles["standard"] != profiles["deepthink"] or \
                       profiles["effort"] == profiles["deepthink"], \
                       f"{peer_id}: standard and deepthink are identical with no fallback justification"
