"""Unit tests for doctor limitation warnings (Wave E).

Detectors are pure functions over (path, env) tested offline and table-driven.
Doctor evaluates the declarative limitations table generically and reports
non-fatal warnings without failing the exit code.
"""
from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from _sys.core.root import find_root

SYS_DIR = find_root(__file__)
if str(SYS_DIR) not in sys.path:
    sys.path.insert(0, str(SYS_DIR))

from core import doctor


class TestDoctorLimitations(unittest.TestCase):
    def test_detect_path_chars_table(self):
        cases = [
            ("C:/Engram/CleanPath", {}, False),
            ("C:/Engram&Tools", {}, True),
            ("C:/Engram%20User", {}, True),
            ("C:/Engram^Folder", {}, True),
            ("C:/Engram!Folder", {}, True),
            ("C:/Engram(x86)", {}, True),
            ("C:/User's Engram", {}, True),
            ("C:/Engram/한글폴더", {}, True),
            ("C:/Engram/café", {}, True),
        ]
        for path_str, env, expected in cases:
            with self.subTest(path=path_str):
                res = doctor.detect_path_chars(path_str, env)
                self.assertEqual(bool(res), expected, f"Failed for path: {path_str}")

    def test_detect_console_codepage_table(self):
        cases = [
            ("C:/Engram", {"CODEPAGE": "65001"}, False),
            ("C:/Engram", {"CODEPAGE": "utf-8"}, False),
            ("C:/Engram", {"CODEPAGE": "949"}, True),
            ("C:/Engram", {"CHCP": "949"}, True),
            ("C:/Engram", {"ACP": "949"}, True),
            ("C:/Engram", {"CODEPAGE": "437"}, True),
            ("C:/Engram", {"CODEPAGE": "1252"}, True),
        ]
        for path_str, env, expected in cases:
            with self.subTest(env=env):
                res = doctor.detect_console_codepage(path_str, env)
                self.assertEqual(bool(res), expected, f"Failed for env: {env}")

    def test_detect_install_path_segment_table(self):
        cases = [
            ("C:/Engram/PortableDev", {}, False),
            ("C:/Users/alice/OneDrive/Engram", {}, True),
            ("C:/Users/alice/OneDrive - Work/Engram", {}, True),
            ("D:/Dropbox/Engram", {}, True),
            ("E:/Google Drive/Engram", {}, True),
            ("C:/SyncFolder/Engram", {"ONEDRIVE": "C:/SyncFolder"}, True),
        ]
        for path_str, env, expected in cases:
            with self.subTest(path=path_str):
                res = doctor.detect_install_path_segment(path_str, env)
                self.assertEqual(bool(res), expected, f"Failed for path: {path_str}")

    def test_detect_path_length_table(self):
        cases = [
            ("C:/Engram", {}, 200, False),
            ("C:/" + "a" * 190, {}, 200, False),
            ("C:/" + "a" * 197, {}, 200, True),
            ("C:/" + "a" * 240, {}, 200, True),
        ]
        for path_str, env, threshold, expected in cases:
            with self.subTest(path_len=len(path_str)):
                res = doctor.detect_path_length(path_str, env, threshold=threshold)
                self.assertEqual(bool(res), expected, f"Failed for length: {len(path_str)}")

    def test_declarative_limitations_file_exists_and_has_required_entries(self):
        lim_file = SYS_DIR / "limitations.json"
        self.assertTrue(lim_file.exists(), f"{lim_file} does not exist")
        data = json.loads(lim_file.read_text(encoding="utf-8"))
        entries = data if isinstance(data, list) else data.get("limitations", [])
        self.assertGreaterEqual(len(entries), 4)

        kinds = {e.get("kind") or e.get("detector") for e in entries}
        self.assertIn("path-chars", kinds)
        self.assertIn("console-codepage", kinds)
        self.assertIn("install-path-segment", kinds)
        self.assertTrue("path-length" in kinds or "max-path" in kinds)

        for entry in entries:
            self.assertIn("id", entry)
            self.assertIn("message", entry)
            self.assertTrue("remedy" in entry or "remedy-in-one-line" in entry)

    def test_evaluate_limitations_generic(self):
        table = [
            {
                "id": "test_path",
                "kind": "path-chars",
                "message": "Bad chars",
                "remedy": "Fix chars",
            },
            {
                "id": "test_cp",
                "kind": "console-codepage",
                "message": "Bad codepage",
                "remedy": "Fix codepage",
            },
        ]
        warnings = doctor.evaluate_limitations(
            base_dir="C:/Engram&Special",
            sys_dir=SYS_DIR,
            env={"CODEPAGE": "949"},
            table=table,
        )
        self.assertEqual(len(warnings), 2)
        warn_ids = [w["id"] for w in warnings]
        self.assertIn("test_path", warn_ids)
        self.assertIn("test_cp", warn_ids)
        for w in warnings:
            self.assertIn("message", w)
            self.assertIn("remedy", w)

    def test_doctor_run_never_fails_for_warnings_json(self):
        ctx = {
            "base_dir": "C:/Engram&Special",
            "sys_dir": SYS_DIR,
            "args": ["--json"],
            "env": {"CODEPAGE": "949"},
        }
        with patch.object(doctor, "check_python", return_value={"name": "python", "ok": True, "level": "ok", "detail": "ok"}):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                res = doctor.run(ctx)
                self.assertEqual(res["status"], "success")
                self.assertIn("warnings", res)
                self.assertGreater(len(res["warnings"]), 0)

                output_json = json.loads(mock_out.getvalue())
                self.assertEqual(output_json["status"], "success")
                self.assertIn("warnings", output_json)
                self.assertGreater(len(output_json["warnings"]), 0)

    def test_doctor_run_prints_warn_lines_in_human_output(self):
        ctx = {
            "base_dir": "C:/Engram&Special",
            "sys_dir": SYS_DIR,
            "args": [],
            "env": {"CODEPAGE": "949"},
        }
        with patch.object(doctor, "check_python", return_value={"name": "python", "ok": True, "level": "ok", "detail": "ok"}):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                res = doctor.run(ctx)
                self.assertEqual(res["status"], "success")
                out = mock_out.getvalue()
                self.assertIn("WARN", out)
                self.assertIn("Remedy:", out)


if __name__ == "__main__":
    unittest.main()
