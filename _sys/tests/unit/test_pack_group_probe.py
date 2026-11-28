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
        from optional_pack_group import initialize_fixture
        initialize_fixture(self.root)

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
            self.assertEqual(recover(self.root, descriptor, mode)["phase"],
                             "ROLLED_BACK" if mode == "rollback" else "COMMITTED")
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
        self.assertEqual([p.name for p in self.root.iterdir()], ["fixture-root.txt"])

    def test_non_fixture_root_is_rejected_before_lifecycle_access(self):
        from optional_pack_group import publish
        foreign = self.root / "foreign"
        foreign.mkdir()
        sentinel = foreign / "env.manifest.json"
        sentinel.write_bytes(b"user data")
        with self.assertRaises(ValueError):
            publish(foreign, CATALOG[0], 0, "runtime-a", *archive(b"bytes"))
        self.assertEqual(list(foreign.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"user data")

    def test_process_exit_after_runtime_write_before_acknowledgement(self):
        import subprocess
        from optional_pack_group import activate, publish, recover
        descriptor = CATALOG[-1]
        publish(self.root, descriptor, 0, "runtime-a", *archive(b"old"))
        payload, digest = archive(b"new")
        child = """
import os
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from pack_catalog import load_fixtures
from optional_pack_group import publish
from core import env_manifest
original = env_manifest._atomic_write_text
def stop_after_runtime(path, text):
    original(path, text)
    if path.name == 'runtime.json':
        os._exit(73)
env_manifest._atomic_write_text = stop_after_runtime
descriptor, = load_fixtures([Path(sys.argv[2])])
publish(Path(sys.argv[3]), descriptor, 1, 'runtime-b', bytes.fromhex(sys.argv[4]), sys.argv[5])
"""
        proc = subprocess.run([sys.executable, "-B", "-c", child, str(REPO / "tools/feasibility"),
                               str(FIXTURES / "gamma.descriptor.json"), str(self.root), payload.hex(), digest],
                              capture_output=True, timeout=15)
        self.assertEqual(proc.returncode, 73, proc.stderr)
        with self.assertRaises(ValueError):
            activate(self.root, descriptor)
        self.assertEqual(recover(self.root, descriptor, "resume")["phase"], "COMMITTED")
        self.assertEqual(activate(self.root, descriptor), (2, "runtime-b", b"new"))

    def test_unreadable_journal_blocks_even_a_coherent_pointer_pair(self):
        from core.env_ops import journal_path
        from optional_pack_group import activate, publish
        descriptor = CATALOG[-1]
        publish(self.root, descriptor, 0, "runtime-a", *archive(b"payload"))
        journal = journal_path(self.root)
        journal.write_bytes(b"torn first record")
        with self.assertRaises(ValueError):
            activate(self.root, descriptor)
        with self.assertRaises(ValueError):
            publish(self.root, descriptor, 1, "runtime-b", *archive(b"new"))
        self.assertEqual(journal.read_bytes(), b"torn first record")

    def test_process_handoff_holds_the_lock_and_uses_verified_fixture_bytes(self):
        from unittest.mock import patch
        import subprocess
        from core import env_lock
        from optional_pack_group import launch, publish
        descriptor = CATALOG[-1]
        publish(self.root, descriptor, 0, "runtime-a", *archive(b"verified fixture"))
        run = subprocess.Popen

        def spawn(*args, **kwargs):
            self.assertEqual(env_lock.inspect(self.root)["state"], "held")
            attempt = publish(self.root, descriptor, 1, "runtime-b", *archive(b"new"))
            self.assertEqual(attempt["exit_code"], 11)
            child = run(*args, **kwargs)
            communicate = child.communicate

            def wait(*args, **kwargs):
                self.assertEqual(env_lock.inspect(self.root)["state"], "free")
                result = publish(self.root, descriptor, 1, "runtime-b", *archive(b"new"))
                self.assertEqual(result["phase"], "COMMITTED")
                return communicate(*args, **kwargs)

            child.communicate = wait
            return child

        with patch("optional_pack_group.subprocess.Popen", side_effect=spawn):
            launched = launch(self.root, descriptor)
        self.assertEqual(launched, {"revision": 1, "runtime": "runtime-a",
                                    "sha256": sha256(b"verified fixture").hexdigest()})
        self.assertEqual(env_lock.inspect(self.root)["state"], "free")
        from optional_pack_group import activate
        self.assertEqual(activate(self.root, descriptor), (2, "runtime-b", b"new"))

    def test_launch_refuses_active_journal_without_spawning(self):
        from unittest.mock import patch
        from core.env_ops import SimulatedCrash
        from optional_pack_group import launch, publish
        descriptor = CATALOG[-1]
        with self.assertRaises(SimulatedCrash):
            publish(self.root, descriptor, 0, "runtime-a", *archive(b"fixture"),
                    crash_after="fixture-package")
        with patch("optional_pack_group.subprocess.Popen") as spawn:
            with self.assertRaises(ValueError):
                launch(self.root, descriptor)
        spawn.assert_not_called()

    def test_retirement_is_recoverable_and_reinstall_requires_retained_revision(self):
        from core.env_ops import SimulatedCrash
        from optional_pack_group import activate, publish, recover, retire

        descriptor = CATALOG[-1]
        other = CATALOG[0]
        data = self.root / descriptor.slot_rel / "workspaces" / "kept.txt"
        data.parent.mkdir(parents=True)
        data.write_bytes(b"original workspace")
        publish(self.root, descriptor, 0, "runtime-a", *archive(b"first"))
        publish(self.root, other, 0, "runtime-a", *archive(b"other"))

        for interrupted, decision in (("fixture-runtime", "rollback"), ("fixture-package", "resume")):
            with self.assertRaises(SimulatedCrash):
                retire(self.root, descriptor, 1, b"first", crash_after=interrupted)
            with self.assertRaisesRegex(ValueError, "recovery"):
                activate(self.root, descriptor)
            recover(self.root, descriptor, decision)
            expected = (1, "runtime-a", b"first") if decision == "rollback" else None
            self.assertEqual(activate(self.root, descriptor), expected)

        for revision, reuse in ((0, False), (1, True), (2, False)):
            with self.assertRaises(ValueError):
                publish(self.root, descriptor, revision, "runtime-a", *archive(b"new"),
                        reuse_retained=reuse)
        reinstall = publish(self.root, descriptor, 2, "runtime-a", *archive(b"new"), reuse_retained=True)
        self.assertEqual(reinstall["phase"], "COMMITTED")
        self.assertEqual(activate(self.root, descriptor), (3, "runtime-a", b"new"))
        self.assertEqual(activate(self.root, other), (1, "runtime-a", b"other"))
        self.assertEqual(data.read_bytes(), b"original workspace")
