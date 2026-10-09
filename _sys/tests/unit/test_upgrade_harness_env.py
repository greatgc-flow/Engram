"""Harness children receive the product's declarative runtime environment."""
import json
import unittest
from unittest.mock import patch

from tools.release_gate import upgrade_harness


class UpgradeHarnessEnvironmentTests(unittest.TestCase):
    def test_subprocess_environment_enables_utf8_from_product_manifest(self):
        with patch.dict("os.environ", {"PYTHONUTF8": "0"}, clear=True):
            env = upgrade_harness.build_subprocess_env({"CANDIDATE": "fixture"})
        self.assertEqual(env["PYTHONUTF8"], "1")
        self.assertEqual(env["CANDIDATE"], "fixture")
        declared = json.loads(
            (upgrade_harness._SYS_DIR_DEFAULT / "env.json").read_text(encoding="utf-8")
        )["env_vars"]
        for key, value in declared.items():
            self.assertEqual(env[key], str(value))


if __name__ == "__main__":
    unittest.main()
