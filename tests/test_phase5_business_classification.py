from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_experience_dashboard.py"


def load_module():
    spec = importlib.util.spec_from_file_location("phase5_dashboard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def card(card_type: str, *texts: str) -> dict:
    return {
        "cardId": "C1",
        "卡片类型": card_type,
        "regions": [{
            "name": "履约区",
            "elements": [
                {"内容简述": text, "textFacts": {"semanticRole": "fulfillment"}}
                for text in texts
            ],
        }],
    }


class Phase5BusinessClassificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_shared_fulfillment_word_is_not_a_business_decision(self) -> None:
        result = self.module.classify_card(card("商家卡片-文字下挂", "原文:外卖", "原文:配送费¥2"))
        self.assertEqual(result["scope"], "unknown")

    def test_product_card_with_shared_fulfillment_is_flash_delivery(self) -> None:
        result = self.module.classify_card(card("商品卡片", "原文:外卖", "原文:配送费¥2"))
        self.assertEqual(result["businessCode"], "flash_delivery")

    def test_food_semantics_classify_without_query_override(self) -> None:
        result = self.module.classify_card(card("商家卡片-文字下挂", "原文:外卖", "原文:火锅餐厅"))
        self.assertEqual(result["businessCode"], "food_delivery")
        self.assertFalse(hasattr(self.module, "REPORT_QUERY_BUSINESS_OVERRIDES"))

