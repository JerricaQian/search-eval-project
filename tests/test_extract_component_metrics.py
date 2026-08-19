from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "scripts" / "extract_component_metrics.py"


def load_module():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("extract_component_metrics_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class ExtractComponentMetricsTest(unittest.TestCase):
    def test_icon_measurement_traverses_atoms_without_visual_inventory(self) -> None:
        module = load_module()
        import numpy as np
        elements = [
            {"id": "kept", "坐标": [0, 0, 20, 20], "visual": {"entityKind": "icon", "visualStatus": "confirmed"}},
            {"id": "uncertain", "坐标": [30, 0, 20, 20], "visual": {"entityKind": "icon", "visualStatus": "uncertain"}},
        ]
        image = np.full((40, 60, 3), 255, dtype=np.uint8)
        result = module.derive_icon_styles(image, elements, np.zeros((40, 60), dtype=np.uint8))
        self.assertEqual([item["id"] for item in result["iconEntities"]], ["kept"])
        self.assertFalse(result["measurementComplete"])
        self.assertEqual(result["unmeasuredAtomicIconIds"], ["kept"])
        self.assertEqual(result["countSource"], "phase3.pixel_measurement_within_phase2_icon_atoms")


if __name__ == "__main__":
    unittest.main()
