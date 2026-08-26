from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "phase5-report" / "scripts" / "build_experience_dashboard.py"


def load_module():
    spec = importlib.util.spec_from_file_location("phase5_dashboard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def card(card_type: str, semantic: tuple[str, ...] = (), fulfillment: tuple[str, ...] = ()) -> dict:
    return {
        "cardId": "C1",
        "卡片类型": card_type,
        "regions": [{
            "name": "标题区",
            "elements": [
                {"内容简述": text, "textFacts": {"semanticRole": "title"}}
                for text in semantic
            ],
        }, {
            "name": "履约区",
            "elements": [
                {"内容简述": text, "textFacts": {"semanticRole": "fulfillment"}}
                for text in fulfillment
            ],
        }],
    }


class Phase5BusinessClassificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_merchant_semantics_and_delivery_classify_as_food_delivery(self) -> None:
        result = self.module.classify_card(card("商家卡片-文字下挂", ("原文:火锅餐厅",), ("原文:外卖", "原文:配送费¥2")))
        self.assertEqual(result["businessCode"], "food_delivery")

    def test_product_card_with_shared_fulfillment_is_flash_delivery(self) -> None:
        result = self.module.classify_card(card("商品卡片", ("原文:矿泉水",), ("原文:外卖", "原文:配送费¥2")))
        self.assertEqual(result["businessCode"], "flash_delivery")

    def test_flash_delivery_covers_visible_daily_goods_and_fresh_product_terms(self) -> None:
        for product in ("原文:安睡裤", "原文:卫生巾", "原文:泰国金枕榴莲"):
            with self.subTest(product=product):
                result = self.module.classify_card(card("商品卡片", (product,), ("原文:外卖",)))
                self.assertEqual(result["businessCode"], "flash_delivery")

    def test_food_semantics_classify_without_query_override(self) -> None:
        result = self.module.classify_card(card("商家卡片-文字下挂", ("原文:火锅餐厅",), ("原文:到店团购",)))
        self.assertEqual(result["businessCode"], "dine_in")
        self.assertFalse(hasattr(self.module, "REPORT_QUERY_BUSINESS_OVERRIDES"))

    def test_named_business_semantics_take_priority_over_fulfillment(self) -> None:
        result = self.module.classify_card(card("商品卡片", ("原文:连锁药房",), ("原文:分钟达",)))
        self.assertEqual(result["businessCode"], "healthcare")

    def test_all_supported_businesses_have_a_deterministic_card_rule(self) -> None:
        cases = [
            ("到餐", card("商家卡片-文字下挂", ("原文:火锅餐厅",), ("原文:到店团购",)), "dine_in"),
            ("餐饮外卖", card("商家卡片-文字下挂", ("原文:火锅餐厅",), ("原文:外卖配送",)), "food_delivery"),
            ("闪购", card("商品卡片", ("原文:咖啡豆",), ("原文:外卖配送",)), "flash_delivery"),
            ("小象超市", card("商家卡片-文字下挂", ("原文:小象超市",), ("原文:分钟达",)), "xiaoxiang"),
            ("医药健康", card("商品卡片", ("原文:连锁药房",), ("原文:分钟达",)), "healthcare"),
            ("酒店旅行", card("商家卡片-文字下挂", ("原文:精品酒店",), ()), "hotel_travel"),
            ("服务零售", card("商家卡片-文字下挂", ("原文:专业理发",), ("原文:预约",)), "service_retail"),
            ("猫眼", card("商家卡片-文字下挂", ("原文:电影票",), ("原文:场次",)), "maoyan"),
        ]
        for name, input_card, expected in cases:
            with self.subTest(business=name):
                self.assertEqual(self.module.classify_card(input_card)["businessCode"], expected)

    def test_flash_delivery_requires_delivery_and_a_flash_category(self) -> None:
        self.assertEqual(
            self.module.classify_card(card("商品卡片", ("原文:矿泉水",), ()))["businessCode"],
            "unknown",
        )
        self.assertEqual(
            self.module.classify_card(card("商品卡片", ("原文:矿泉水",), ("原文:外卖配送",)))["businessCode"],
            "flash_delivery",
        )
        self.assertEqual(
            self.module.classify_card(card("商品卡片", ("原文:奶茶",), ("原文:外卖配送",)))["businessCode"],
            "food_delivery",
        )

    def test_unclassified_merchant_card_blocks_business_dashboard(self) -> None:
        result = self.module.classify_card(card("商家卡片-文字下挂", ("原文:某商户",), ()))
        self.assertEqual(result["businessCode"], "unknown")
        with self.assertRaisesRegex(ValueError, "无法由当前商卡语义与履约事实判定"):
            self.module.validate_dataset({
                "queryCount": 1,
                "queryDetails": {"测试": [{"rating": "未执行", "issues": []}]},
                "unknown": [{"query": "测试", "cardId": "C1", "reason": "证据不足"}],
                "businesses": [],
                "groups": [],
            }, Path("/tmp"), set())

    def test_phase2_explicit_business_ownership_has_priority(self) -> None:
        input_card = card("商品卡片", ("原文:火锅餐厅",), ("原文:外卖配送",))
        input_card.update({"ownershipScope": "business", "businessCode": "healthcare"})
        result = self.module.classify_card(input_card)
        self.assertEqual(result["businessCode"], "healthcare")
        self.assertEqual(result["confidence"], "phase2_explicit")

    def test_unsupported_phase2_business_ownership_stays_unknown(self) -> None:
        input_card = card("商品卡片", ("原文:火锅餐厅",), ("原文:外卖配送",))
        input_card.update({"ownershipScope": "business", "businessCode": "made_up_business"})
        result = self.module.classify_card(input_card)
        self.assertEqual(result["businessCode"], "unknown")
        self.assertIn("unsupported_explicit_business_code", result["confidence"])

    def test_positive_redundancy_metrics_are_rendered_as_problem_names(self) -> None:
        self.assertEqual(self.module.METRICS["eval-8-info-redundancy"][0], "信息冗余")
        self.assertEqual(self.module.METRICS["eval-7-info-redundancy"][0], "功能/信息冗余")
