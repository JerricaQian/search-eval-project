from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import numpy as np


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "phase3-single_element-eval" / "eval-skills" / "eval-2-color-logic-single-element" / "scripts" / "count_element_colors.py"


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


if __name__ == "__main__":
    unittest.main()
