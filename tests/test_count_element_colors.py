from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "phase3-evaluation" / "dimensions" / "single-element" / "skills" / "eval-2-color-logic-single-element" / "scripts" / "count_element_colors.py"


def load_module():
    spec = importlib.util.spec_from_file_location("count_element_colors_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CountElementColorsTest(unittest.TestCase):
    def test_seven_color_bins_use_the_shared_taxonomy(self) -> None:
        module = load_module()
        from color_taxonomy import HUE7_BINS
        self.assertEqual(module.HUE_BINS, list(HUE7_BINS))

    def test_seven_color_bins_merge_yellow_green_and_magenta(self) -> None:
        module = load_module()
        pixels = np.array([
            [128, 255, 0],   # 黄绿归绿
            [255, 0, 255],   # 品红归紫
            [0, 255, 255],   # 青保持青
        ], dtype=np.uint8)
        hue, saturation, value = module.rgb_to_hsv_arr(pixels)
        keys, _ = module.classify(hue, saturation, value)
        self.assertEqual([key.split("-")[0] for key in keys], ["green", "purple", "cyan"])

    def test_debug_mask_and_json_artifact_are_persisted(self) -> None:
        module = load_module()
        image = np.full((20, 20, 3), 255, dtype=np.uint8)
        image[5:15, 5:15] = [255, 80, 20]
        with tempfile.TemporaryDirectory() as tmp:
            debug_path = Path(tmp) / "debug.png"
            count = module.save_debug_mask(image, debug_path, drop_bg=True)
            self.assertTrue(debug_path.is_file())
            self.assertGreater(count, 0)
            debug = np.array(Image.open(debug_path))
            self.assertTrue(np.all(debug[0, 0] == [238, 238, 238]))

    def test_neutral_pixels_do_not_inflate_colour_area_ratio(self) -> None:
        module = load_module()
        image = np.full((10, 10, 3), [128, 128, 128], dtype=np.uint8)
        image[0, :5] = [255, 0, 0]
        image[0, 5:] = [0, 0, 255]
        result = module.count_colors(image, min_ratio_pct=40.0)
        self.assertEqual(result["color_count"], 0)
        self.assertEqual(result["chromatic_pixels"], 10)
        self.assertEqual(result["neutral_pixels"], 90)

    def test_tinted_near_black_is_perceptually_neutral(self) -> None:
        module = load_module()
        pixels = np.array([[23, 48, 48], [104, 101, 91]], dtype=np.uint8)
        hue, saturation, value = module.rgb_to_hsv_arr(pixels)
        keys, _ = module.classify(hue, saturation, value)
        self.assertTrue(all(key in module.ACHROMATIC_LABELS for key in keys))


if __name__ == "__main__":
    unittest.main()
