import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "phase2-card-annotation" / "scripts" / "curate_golden_reserve.py"
SPEC = importlib.util.spec_from_file_location("curate_golden_reserve", SCRIPT)
assert SPEC and SPEC.loader
CURATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CURATOR)


class CurateGoldenReserveTest(unittest.TestCase):
    def test_minimal_card_preserves_nested_elements(self) -> None:
        original = {
            "componentType": "result_card",
            "cardType": "商家卡片-文字下挂",
            "coord": [0, 10, 100, 200],
            "regions": {
                "标题区": {
                    "elements": [
                        {
                            "elementType": "商家标题",
                            "visibleText": "示例商家",
                            "coord": [10, 20, 60, 30],
                        }
                    ]
                }
            },
        }

        curated = CURATOR.minimal_card(original)

        self.assertEqual(curated["cardType"], "商家卡片_文字下挂")
        self.assertEqual(curated["regions"], original["regions"])
        self.assertIsNot(curated["regions"], original["regions"])

    def test_minimal_component_preserves_page_elements(self) -> None:
        original = {
            "componentType": "search_bar",
            "elements": [{"elementType": "搜索关键词", "visibleText": "酒店"}],
        }

        curated = CURATOR.minimal_component(original)

        self.assertEqual(curated["elements"], original["elements"])
        self.assertIsNot(curated["elements"], original["elements"])

    def test_hotel_rebuild_outputs_retain_card_regions(self) -> None:
        hotel_root = ROOT / "phase2-card-annotation" / "golden-sample-results" / "hotel-card"
        for path in hotel_root.glob("*.elements.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            cards = [
                card
                for component in payload["pageStructure"]["components"]
                if component.get("componentType") == "results_list"
                for card in component.get("components", [])
            ]
            self.assertTrue(cards, path.name)
            for card in cards:
                self.assertTrue(card.get("regions"), f"{path.name}:card-{card.get('listPosition')}")
            self.assertIn("reviewed_card_elements", payload["verification"]["claimScope"])


if __name__ == "__main__":
    unittest.main()
