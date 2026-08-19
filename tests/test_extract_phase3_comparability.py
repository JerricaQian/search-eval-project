from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "scripts" / "extract_phase3_comparability.py"


def load_module():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("extract_phase3_comparability_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def element(element_id: str, text: str, role: str, x: int, *, cropped: bool = False) -> dict:
    return {
        "id": element_id,
        "元素类型": "文本",
        "内容简述": f"原文:{text}",
        "坐标": [x, 20, 50, 20],
        "isExcluded": False,
        "render": {"visibleStatus": "confirmed", "renderState": "naturally_cropped" if cropped else "normal"},
        "textFacts": {"rawText": text, "semanticRole": role, "fontSizeBucket": "medium"},
        "visual": {"entityKind": "text", "colorRole": "primary"},
    }


class ExtractPhase3ComparabilityTest(unittest.TestCase):
    def test_phase3_derives_candidates_without_phase2_relations(self) -> None:
        module = load_module()
        manifest = {
            "query": "test",
            "cards": [
                {"cardId": "C1", "coord": [0, 0, 200, 200], "structure": {"isResultListItem": True, "comparisonGroupKey": "same"}, "regions": [{"name": "基础信息区", "elements": [element("E1", "4.8分", "rating", 10)]}]},
                {"cardId": "C2", "coord": [0, 200, 200, 200], "structure": {"isResultListItem": True, "comparisonGroupKey": "same"}, "regions": [{"name": "基础信息区", "elements": [element("E2", "好评率98%", "rating", 20)]}]},
            ],
            "relations": [],
        }
        result = module.derive_comparability(manifest)
        self.assertEqual(len(result["comparisons"]), 1)
        comparison = result["comparisons"][0]
        self.assertEqual(comparison["semanticRole"], "rating")
        self.assertTrue(comparison["detectedDifferences"]["format"])
        self.assertTrue(comparison["phase3JudgementRequired"])

    def test_naturally_cropped_value_is_not_used_as_complete_cross_card_value(self) -> None:
        module = load_module()
        manifest = {
            "cards": [
                {"cardId": "C1", "coord": [0, 0, 200, 200], "structure": {"isResultListItem": True, "comparisonGroupKey": "same"}, "regions": [{"name": "价格区", "elements": [element("E1", "¥9.9", "price", 10)]}]},
                {"cardId": "C2", "coord": [0, 200, 200, 200], "structure": {"isResultListItem": True, "comparisonGroupKey": "same"}, "regions": [{"name": "价格区", "elements": [element("E2", "¥1...", "price", 10, cropped=True)]}]},
            ]
        }
        result = module.derive_comparability(manifest)
        self.assertEqual(result["comparisons"], [])


if __name__ == "__main__":
    unittest.main()
