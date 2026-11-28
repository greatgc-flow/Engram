"""Offline group publication crash and rollback oracles on disposable roots."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools/feasibility"))
from pack_catalog import load_fixtures

FIXTURES = REPO / "_sys/tests/fixtures/optional-pack"
CATALOG = load_fixtures(sorted(FIXTURES.glob("*.descriptor.json")))


def archive(payload, name="app.txt"):
    buf = BytesIO()
    with ZipFile(buf, "w") as z:
        z.writestr(name, payload)
    data = buf.getvalue()
    return data, sha256(data).hexdigest()


class GroupProbeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_each_descriptor_uses_same_install_and_update(self):
        from optional_pack_group import activate, publish
        for descriptor in CATALOG:
            publish(self.root, descriptor, 0, "runtime-a", *archive(b"first"))
            self.assertEqual(activate(self.root, descriptor), (1, "runtime-a", b"first"))
        publish(self.root, CATALOG[0], 1, "runtime-b", *archive(b"update"))
        self.assertEqual(activate(self.root, CATALOG[0]), (2, "runtime-b", b"update"))
        for descriptor in CATALOG[1:]:
            self.assertEqual(activate(self.root, descriptor), (1, "runtime-a", b"first"))
        with self.assertRaises(ValueError):
            publish(self.root, CATALOG[0], 1, "runtime-c", *archive(b"stale"))

    def test_recovery_between_pointers_and_after_second_pointer(self):
        from core.env_ops import SimulatedCrash
        from optional_pack_group import activate, publish, recover
        descriptor = CATALOG[-1]
        publish(self.root, descriptor, 0, "runtime-a", *archive(b"old"))
        for step, mode, expected in (("fixture-runtime", "rollback", (1, "runtime-a", b"old")),
                                     ("fixture-package", "resume", (2, "runtime-b", b"new"))):
            with self.assertRaises(SimulatedCrash):
                publish(self.root, descriptor, 1, "runtime-b", *archive(b"new"), crash_after=step)
            with self.assertRaises(ValueError):
                activate(self.root, descriptor)
            self.assertEqual(recover(self.root, descriptor, mode)["status"], "success")
            self.assertEqual(activate(self.root, descriptor), expected)

    def test_foreign_pointer_and_wrong_scope_block_recovery(self):
        from core.env_ops import SimulatedCrash
        from optional_pack_group import activate, publish, recover
        descriptor = CATALOG[-1]
        with self.assertRaises(SimulatedCrash):
            publish(self.root, descriptor, 0, "runtime-a", *archive(b"payload"), crash_after="fixture-runtime")
        with self.assertRaises(ValueError):
            recover(self.root, CATALOG[0], "resume")
        path = self.root / "data/state/fixture-packs/gamma/runtime.json"
        path.write_bytes(b"external edit")
        with self.assertRaises(ValueError):
            recover(self.root, descriptor, "resume")
        self.assertEqual(path.read_bytes(), b"external edit")
        with self.assertRaises(ValueError):
            activate(self.root, descriptor)

    def test_archive_identity_and_member_are_admitted_before_writes(self):
        from optional_pack_group import publish
        payload, _ = archive(b"bytes")
        with self.assertRaises(ValueError):
            publish(self.root, CATALOG[0], 0, "runtime-a", payload, "0"*64)
        with self.assertRaises(ValueError):
            publish(self.root, CATALOG[0], 0, "runtime-a", *archive(b"bytes", "unlisted.txt"))
        self.assertEqual(list(self.root.iterdir()), [])
