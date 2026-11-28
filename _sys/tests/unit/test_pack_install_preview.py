"""Deterministic install previews for frozen descriptor fixtures."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools/feasibility"))
from pack_catalog import load_fixtures

NOW = datetime(2026, 11, 28, tzinfo=timezone.utc)
FIXTURES = REPO / "_sys/tests/fixtures/optional-pack"


class InstallPreviewTests(unittest.TestCase):
    def fixture(self):
        from optional_pack_plan import Evidence, Intent
        descriptors = load_fixtures(sorted(FIXTURES.glob("*.descriptor.json")))
        facts = Evidence("fixture-install", "a"*64, 0, 1, 2, 3, 4096, "ABSENT")
        intent = Intent("op-1", "gen-1", "b"*64, 100, 200, 1200, NOW, NOW + timedelta(hours=1))
        return descriptors, facts, intent

    def test_three_packages_use_one_deterministic_preview(self):
        from optional_pack_plan import install_preview, check_preview
        descriptors, facts, intent = self.fixture()
        for descriptor in descriptors:
            plan = install_preview(descriptor, facts, intent)
            self.assertEqual(plan, install_preview(descriptor, facts, intent))
            self.assertEqual(plan["scope"], [descriptor.package_id])
            self.assertEqual(plan["actions"][0]["target_rel"], descriptor.slot_rel + "/app/generations/gen-1")
            self.assertEqual(plan["required_bytes"], 1500)
            check_preview(plan, descriptor, facts, intent, NOW)

    def test_mutation_stale_facts_and_closed_expiry(self):
        from optional_pack_plan import install_preview, check_preview
        (descriptor, *_), facts, intent = self.fixture()
        plan = install_preview(descriptor, facts, intent)
        plan["actions"][0]["target_rel"] = "foreign/target"
        with self.assertRaises(ValueError):
            check_preview(plan, descriptor, facts, intent, NOW)
        plan = install_preview(descriptor, facts, intent)
        for change in ({"pack_revision": 1}, {"runtime_revision": 2}, {"root_fingerprint": "c"*64},
                       {"trust_revision": 5}, {"policy_revision": 4}, {"installation_id": "other"},
                       {"available_bytes": 1499}, {"slot_status": "UNKNOWN"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                check_preview(plan, descriptor, replace(facts, **change), intent, NOW)
        with self.assertRaises(ValueError):
            check_preview(plan, descriptor, facts, intent, intent.expires_at)
        with self.assertRaises(ValueError):
            check_preview(plan, descriptor, facts, intent, NOW - timedelta(seconds=1))

    def test_invalid_target_or_sizes_and_unresolved_slot(self):
        from optional_pack_plan import install_preview
        (descriptor, *_), facts, intent = self.fixture()
        for change in ({"target_generation": ".."}, {"target_generation": "com1"},
                       {"archive_bytes": -1}, {"expanded_bytes": True}, {"environment_bytes": 2**53},
                       {"expires_at": NOW}, {"created_at": NOW.replace(tzinfo=None)}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                install_preview(descriptor, facts, replace(intent, **change))
        for state in ("CORRUPT", "FOREIGN", "PARTIAL", "DATA_RETAINED"):
            with self.subTest(state=state), self.assertRaises(ValueError):
                install_preview(descriptor, replace(facts, slot_status=state), intent)
