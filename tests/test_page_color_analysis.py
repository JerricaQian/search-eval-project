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
SCRIPT = PROJECT_DIR / "phase3-evaluation" / "dimensions" / "page-framework" / "skills" / "eval-3-page-color-logic" / "scripts" / "page_color_analysis.py"


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

        self.assertEqual(len(result["scope_exclusions"]), 2)
        self.assertEqual(result["n_valid_pixels_before_sample"], 800)

    def test_manifest_scope_excludes_photo_and_restores_system_ui_overlay(self) -> None:
        module = load_module()
        manifest = {
            "cards": [{
                "regions": [{
                    "elements": [
                        {
                            "id": "PHOTO",
                            "coord": [0, 0, 100, 100],
                            "render": {"visibleStatus": "confirmed", "isPhoto": True},
                            "visual": {"entityKind": "image"},
                        },
                        {
                            "id": "BADGE",
                            "coord": [5, 5, 20, 10],
                            "render": {"visibleStatus": "confirmed", "isSystemUi": True},
                            "visual": {"entityKind": "tag"},
                        },
                    ],
                }],
            }],
        }
        exclusions, records, restores, overlays = module.color_scope_from_manifest(manifest)
        self.assertEqual(exclusions, [[0, 100, 0, 100]])
        self.assertEqual(records[0]["elementId"], "PHOTO")
        self.assertEqual(restores, [[5, 15, 5, 25]])
        self.assertEqual(overlays[0]["elementId"], "BADGE")

    def test_page_neutrals_do_not_enter_bins_or_inflate_ratios(self) -> None:
        module = load_module()
        hue = np.concatenate((np.zeros(90), np.zeros(5), np.full(5, 220))).astype(np.float32)
        saturation = np.concatenate((np.zeros(90), np.full(10, 100))).astype(np.float32)
        value = np.full(100, 100, dtype=np.float32)
        result = module.summarize(hue, saturation, value)
        self.assertEqual(result["n_chromatic_pixels"], 10)
        self.assertEqual(result["n_neutral_pixels"], 90)
        self.assertEqual(result["dominant_color_count_7"], 0)


if __name__ == "__main__":
    unittest.main()
