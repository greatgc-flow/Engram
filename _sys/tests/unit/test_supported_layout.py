"""D1: unsupported installs must be left untouched on maintenance/repair."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import layout_migration, repair, updater

WARNING = "WARNING: Unsupported pre-3.2.6 layout: reinstall Engram (your data folders are not touched)."


class SupportedLayoutTests(unittest.TestCase):
    def test_unsupported_layout_paths_leave_data_untouched(self):
        for payload in ('{"layout_version": 1}', '{broken', '[]', '{"layout_version": "2"}', '{"engram_version": "3.2.5"}', None):
            for operation in ("maintenance", "update", "updater", "repair", "repair-json"):
                with self.subTest(payload=payload, operation=operation), tempfile.TemporaryDirectory() as folder:
                    base = Path(folder)
                    sys_dir = base / "_sys"
                    state = sys_dir / "data" / "state"
                    state.mkdir(parents=True)
                    if payload is not None:
                        (state / "layout.json").write_text(payload)
                    (base / ".ai").mkdir()
                    (base / ".ai" / "personal.txt").write_text("keep")
                    before = {str(p.relative_to(base)): p.read_bytes() for p in base.rglob("*") if p.is_file()}
                    out = io.StringIO()
                    err = io.StringIO()
                    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), patch.object(layout_migration, "m1_retire_shipped_files", return_value=(True, {"retired": [], "kept_modified": []})) as retire, patch.object(repair, "detect") as detect:
                        if operation == "maintenance":
                            self.assertEqual(layout_migration.migrate_layout(base, sys_dir), 1)
                        elif operation == "update":
                            result = layout_migration.update_layout({"base_dir": base, "sys_dir": sys_dir, "args": ["--yes"]})
                            self.assertEqual(result["status"], "failed")
                        elif operation == "updater":
                            with patch.object(updater, "_SYS_DIR", sys_dir), patch.object(updater, "_PORTABLE_ROOT", base), patch.object(updater.provisioner, "load_json_with_fallback", side_effect=AssertionError("Unsupported layout reached discovery")) as load:
                                result = updater.run({"args": ["--yes"]})
                                self.assertEqual(result["status"], "failed")
                                load.assert_not_called()
                        else:
                            result = repair.repair_main({"base_dir": base, "sys_dir": sys_dir, "args": ["--apply", "--yes"] + (["--json"] if operation == "repair-json" else [])})
                            self.assertEqual(result["exit_code"], 11)
                        retire.assert_not_called()
                        detect.assert_not_called()
                    self.assertEqual((err if operation == "repair-json" else out).getvalue().splitlines(), [WARNING])
                    self.assertEqual(before, {str(p.relative_to(base)): p.read_bytes() for p in base.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
