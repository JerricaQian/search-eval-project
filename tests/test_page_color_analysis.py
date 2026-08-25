from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "phase3-page_framework-eval" / "eval-skills" / "eval-3-page-color-logic" / "scripts" / "page_color_analysis.py"


def load_module():
    spec = importlib.util.spec_from_file_location("page_color_analysis_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PageColorAnalysisTest(unittest.TestCase):
    def test_seven_color_bins_use_the_shared_taxonomy(self) -> None:
        module = load_module()
        from color_taxonomy import hue7_ranges
        self.assertEqual(module.HUE_FAMILIES_7, hue7_ranges())

    def test_36_color_keeps_magenta_but_seven_color_merges_it_to_purple(self) -> None:
        module = load_module()
        hue = np.full(100, 300.0, dtype=np.float32)
        self.assertIn("magenta", module.count_families(hue, module.HUE_FAMILIES_36, 100))
        self.assertIn("purple", module.count_families(hue, module.HUE_FAMILIES_7, 100))
        self.assertNotIn("red", module.count_families(hue, module.HUE_FAMILIES_7, 100))

    def test_total_colour_uses_36_cells_not_nine_hue_families(self) -> None:
        module = load_module()
        hue = np.array([5.0, 5.0], dtype=np.float32)
        value = np.array([90.0, 35.0], dtype=np.float32)
        cells = module.count_color_cells_36(hue, value, 2)
        self.assertEqual(set(cells), {"red-light", "red-dark"})

    def test_manifest_excludes_tab_and_filter_modules(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = np.zeros((40, 40, 3), dtype=np.uint8)
            image[:10, :] = (0, 0, 255)
            image[10:20, :] = (0, 255, 0)
            image[20:, :] = (255, 0, 0)
            image_path = root / "漂流_全部_1.png"
            cv2.imwrite(str(image_path), image)
            manifest = root / "elements.json"
            manifest.write_text(json.dumps({"pageFacts": {"modules": [
                {"id": "M1", "moduleType": "tab", "coord": [0, 0, 40, 10]},
                {"id": "M2", "moduleType": "sort_filter", "coord": [0, 10, 40, 10]},
            ]}}, ensure_ascii=False), encoding="utf-8")
            result = module.analyze_page(str(image_path), manifest=str(manifest))

        self.assertEqual(len(result["excluded_page_modules"]), 2)
        self.assertEqual(result["n_valid_pixels_before_sample"], 800)


if __name__ == "__main__":
    unittest.main()
