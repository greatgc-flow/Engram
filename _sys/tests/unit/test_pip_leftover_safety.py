"""Safety regressions runnable with python -m unittest, without pytest."""
import json
import shutil
import uuid
import unittest
from pathlib import Path
from unittest.mock import patch

from core import backups, env_ops, repair, venv_manager


class PipSafety(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[3] / ("pip_scratch_" + uuid.uuid4().hex)
        scratch.mkdir()
        self.addCleanup(shutil.rmtree, scratch)
        self.install = scratch / "_sys"
        self.site = self.install / "env/venv/Lib/site-packages"
        self.site.mkdir(parents=True)
        self.info = self.metadata("peerhub-1.dist-info", "peerhub/__init__.py")
        self.old = self.metadata("~eerhub.dist-info", "peerhub/__init__.py")
        (self.site / "peerhub").mkdir()
        (self.site / "peerhub/__init__.py").write_text("working")

    def metadata(self, dirname, record, name="peerhub", top="peerhub"):
        info = self.site / dirname
        info.mkdir(parents=True)
        (info / "METADATA").write_text(f"Name: {name}\n")
        (info / "top_level.txt").write_text(top + "\n")
        (info / "RECORD").write_text(record + ",,\n")
        return info

    def row(self):
        return next(r for r in venv_manager.pip_leftovers(self.site)
                    if r["leftover"] == str(self.old))

    def plan(self):
        return repair.build_plan(self.install, self.install.parent,
            {"manifest": "ok", "drift": {}, "findings": [
                {"name": "pip_leftovers", "level": "warning"}]}, only={"venv"})

    def test_1_partial_record_kept(self):
        (self.info / "RECORD").write_text("peerhub/missing.py,,\n")
        self.assertFalse(self.row()["removable"])
        self.assertIn("force-reinstall", self.row()["remedy"])

    def test_1_namespace_collision_kept(self):
        (self.info / "RECORD").write_text("peerhub/,,\n")
        self.metadata("other-1.dist-info", "peerhub/other.py", "other")
        self.assertFalse(self.row()["removable"])

    def test_1_missing_record_inconclusive(self):
        (self.info / "RECORD").unlink()
        self.assertFalse(self.row()["removable"])

    def test_1_optional_record_entries(self):
        (self.info / "RECORD").write_text("peerhub/__init__.py,,\n" + "\n".join(
            f"{self.info.name}/{name},," for name in (
                "INSTALLER", "RECORD", "REQUESTED", "direct_url.json", "top_level.txt")) +
            "\npeerhub/__pycache__/gone.pyc,,\npeerhub/gone.pyc,,\n")
        (self.info / "top_level.txt").unlink()
        self.assertTrue(self.row()["removable"])

    def test_1_recorded_namespace_file_is_proof(self):
        self.metadata("other-1.dist-info", "peerhub/other.py", "other")
        self.assertTrue(self.row()["removable"])

    def test_2_nested_user_archive_kept(self):
        self.metadata("~archive/nested.dist-info", "peerhub/__init__.py")
        row = next(r for r in venv_manager.pip_leftovers(self.site)
                   if Path(r["leftover"]).name == "~archive")
        self.assertFalse(row["removable"])
        self.assertEqual(row["remedy"], "unrecognized, inspect manually")

    def test_2_top_level_pip_evidence(self):
        recognized = self.metadata("~package", "peerhub/__init__.py")
        arbitrary = self.metadata("~user", "peerhub/__init__.py")
        (arbitrary / "RECORD").unlink()
        rows = {r["leftover"]: r for r in venv_manager.pip_leftovers(self.site)}
        self.assertTrue(rows[str(recognized)]["removable"])
        self.assertFalse(rows[str(arbitrary)]["removable"])

    def test_3_extensions_and_cache(self):
        for suffix in (".cp313-win_amd64.pyd", ".abi3.so"):
            with self.subTest(suffix=suffix):
                (self.site / ("native" + suffix)).write_bytes(b"extension")
                (self.info / "top_level.txt").write_text("native\n")
                (self.info / "RECORD").write_text(
                    f"native{suffix},,\n__pycache__/native.pyc,,\n")
                self.assertTrue(self.row()["removable"])

    def test_4_undo_identity(self):
        step = self.plan()["steps"][0]
        ctx = env_ops.OpContext(self.install, "test-op", "repair", {}, {})
        with patch("core.python_manager.default_holders", return_value=[]):
            step.do(ctx)
            ref = backups.scan(self.install).valid[0]
            for key in ("op_id", "source_path"):
                original = ref.meta[key]
                ref.meta[key] = "wrong"
                backups._write_meta(ref.path, ref.meta)
                with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                    step.undo(ctx)
                self.assertFalse(self.old.exists())
                ref.meta[key] = original
            backups._write_meta(ref.path, ref.meta)
            step.undo(ctx)
            self.assertTrue(self.old.exists())

    def test_4_locked_move_rolls_back(self):
        second = self.metadata("~second.dist-info", "peerhub/__init__.py")
        plan = self.plan()
        move = backups._move_dir
        for error in (PermissionError("external AV lock"), OSError("move failed"),
                      OSError(22, "path too long", None, 206)):
            with self.subTest(error=error):
                def locked(src, dst, **kwargs):
                    if src == second:
                        raise error
                    return move(src, dst, **kwargs)
                with patch("core.python_manager.default_holders", return_value=[]), \
                        patch.object(backups, "_move_dir", side_effect=locked):
                    result = env_ops.execute(self.install, "repair", plan["steps"])
                self.assertNotEqual(result["exit_code"], 0)
                self.assertTrue(self.old.exists() and second.exists())
                self.assertFalse(any(r.meta["state"] == "pending"
                                     for r in backups.scan(self.install).valid))

    def test_5_long_destination_kept(self):
        step = self.plan()["steps"][0]
        ctx = env_ops.OpContext(self.install, "test-op", "repair", {}, {})
        root = self.install / ("x" * 180)
        with patch("core.python_manager.default_holders", return_value=[]), \
                patch.object(backups, "backups_root", return_value=root):
            step.do(ctx)
        self.assertTrue(self.old.exists())
        self.assertIn("path too long to quarantine safely", json.dumps(ctx.data))


if __name__ == "__main__":
    unittest.main()
