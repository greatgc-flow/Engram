"""Display adapter discovery is independent of inference eligibility."""
import importlib.util
from pathlib import Path
from unittest import TestCase


class AdapterInventoryTests(TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[3] / "tools/feasibility/windows_accelerators.py"
        spec = importlib.util.spec_from_file_location("accelerators", path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_mixed_adapters_and_duplicate_names_stay_separate(self):
        names = ["Integrated GPU", "Vendor A graphics", "Vendor B graphics", "Vendor B graphics"]
        rows = [{"Name": name, "DriverVersion": "1.0"} for name in names]
        data = self.module.inventory(rows)
        self.assertEqual([a["name"] for a in data["adapters"]], names)
        self.assertEqual(data["coverage"], "MEASURED")
        for adapter in data["adapters"]:
            self.assertIsNone(adapter["available_bytes"])
            self.assertEqual(adapter["inference"], "NOT_RUN")

    def test_no_adapter_differs_from_failed_probe(self):
        self.assertEqual(self.module.inventory([])["coverage"], "MEASURED")
        self.assertEqual(self.module.inventory(None)["coverage"], "UNKNOWN")

    def test_bad_shape_never_proves_absence(self):
        for value in ({}, [None], [{"DriverVersion":"1.0"}]):
            self.assertEqual(self.module.inventory(value)["coverage"], "UNKNOWN")
