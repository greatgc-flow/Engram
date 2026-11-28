"""Read-only fixture registry checks across two known slots and a third package."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "_sys/tests/fixtures/optional-pack"
PROBE = REPO / "tools/feasibility/pack_catalog.py"


class RegistryProbeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.registry = self.root / "data/state/package-registry.json"
        self.registry.parent.mkdir(parents=True)
        self.doc = json.loads((FIXTURES / "registry/mixed.registry.json").read_bytes())
        self.marker = self.root / "AI/state/ownership.json"
        self.marker.parent.mkdir(parents=True)
        receipt = {"installation_id": "fixture-install", "package_id": "ai", "slot_rel": "AI"}
        raw = json.dumps(receipt).encode()
        self.marker.write_bytes(raw)
        self.doc["entries"][0]["ownership_receipt_sha256"] = hashlib.sha256(raw).hexdigest()

    def run_probe(self, owner="fixture-install"):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        args = [sys.executable, "-B", str(PROBE), "--installation-id", owner,
                str(self.root), *map(str, sorted(FIXTURES.glob("*.descriptor.json")))]
        proc = subprocess.run(args, capture_output=True, text=True, timeout=15)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        return json.loads(proc.stdout)

    def write_registry(self):
        self.registry.write_text(json.dumps(self.doc), encoding="utf-8")

    def test_owned_retained_and_unverified_install_are_distinct(self):
        self.write_registry()
        self.assertEqual(self.run_probe(), {"ai": "DATA_RETAINED", "contentflow": "PARTIAL", "gamma": "ABSENT"})
        self.marker.unlink()
        self.assertEqual(self.run_probe()["ai"], "PARTIAL")

    def test_foreign_copied_ownership(self):
        self.write_registry()
        self.assertEqual(set(self.run_probe("other-install").values()), {"FOREIGN"})
        self.marker.write_text(json.dumps({"installation_id": "foreign", "package_id": "ai", "slot_rel": "AI"}),
                               encoding="utf-8")
        self.assertEqual(self.run_probe()["ai"], "FOREIGN")

    def test_semantically_invalid_or_torn_registry_is_corrupt(self):
        for raw in ((FIXTURES / "registry/retained-active.semantic-negative.json").read_bytes(),
                    b'{"revision":1,"revision":2}', b'{"torn'):
            self.registry.write_bytes(raw)
            self.assertEqual(set(self.run_probe().values()), {"CORRUPT"})
        self.doc["entries"].append(self.doc["entries"][0])
        self.write_registry()
        self.assertEqual(set(self.run_probe().values()), {"CORRUPT"})

    def test_unregistered_slot_has_no_ownership(self):
        self.assertEqual(self.run_probe(), {"ai": "UNKNOWN", "contentflow": "ABSENT", "gamma": "ABSENT"})
