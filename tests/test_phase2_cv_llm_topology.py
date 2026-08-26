import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "phase2-card-annotation" / "scripts")
sys.path.insert(0, SCRIPTS)

from apply_visual_review import apply  # noqa: E402
from build_phase2_manifest import append_item_groups  # noqa: E402
from card_contract_engine import extract_features  # noqa: E402
from card_type_registry import load_registry, validate_phase2_taxonomy  # noqa: E402
from run_phase2_recognition import run, validate_cv_llm_visual_review  # noqa: E402

sys.path.remove(SCRIPTS)


class CvLlmTopologyTests(unittest.TestCase):
    def test_phase2_taxonomy_uses_the_shared_card_type_registry(self):
        taxonomy = json.loads((ROOT / "phase2-card-annotation" / "references" / "search_card_taxonomy.v1.json").read_text(encoding="utf-8"))
        validate_phase2_taxonomy(taxonomy)
        registry_ids = {item["id"] for item in load_registry()["resultCardTypes"]}
        self.assertEqual(registry_ids, {item["id"] for item in taxonomy["cardTypes"]})

    def test_visual_review_publishes_declared_topology_not_geometry_guess(self):
        screenshot = ROOT / "screenshots" / "药店_全部_1_副本.png"
        facts = {"screenshot": str(screenshot), "candidates": {"text": [], "photos": []}, "routing": {}}
        review = {
            "screenshot": str(screenshot),
            "cards": [{
                "cardId": "C1", "coord": [0, 500, 1224, 600], "cardTypeCandidate": "商家卡片_图文下挂",
                "topology": {
                    "regions": [
                        {"slot": "merchant_head", "coord": [24, 520, 180, 180]},
                        {"slot": "merchant_info", "coord": [220, 520, 700, 180]},
                        {"slot": "attached_goods", "coord": [220, 720, 900, 240]},
                    ],
                    "attachedItems": [{"itemIndex": 1, "coord": [220, 720, 180, 240], "visibleStatus": "confirmed"}],
                },
                "fields": [{"text": "示例商家", "coord": [220, 530, 220, 36], "role": "title", "colorRole": "neutral"}],
                "photos": [
                    {"coord": [24, 520, 180, 180]},
                    {"coord": [220, 720, 180, 180]},
                ],
            }],
            "modules": [],
        }
        result = apply(facts, review)
        slots = [item["visualReview"]["topologySlot"] for item in result["candidates"]["photos"]]
        self.assertEqual(slots, ["merchant_head", "attached_goods"])
        self.assertEqual(result["candidates"]["text"][0]["visualReview"]["topologySlot"], "merchant_info")

    def test_declared_graphic_merchant_topology_is_a_contract_feature(self):
        facts = {
            "viewport": {"width": 1224, "height": 2700},
            "candidates": {
                "text": [{"coord": [220, 520, 230, 30], "text": "示例商家", "route": "accepted"}],
                "photos": [
                    {"coord": [24, 520, 180, 180], "route": "accepted"},
                    {"coord": [220, 720, 180, 200], "route": "accepted"},
                ],
            },
        }
        card = {
            "coord": [0, 500, 1224, 600], "status": "confirmed", "evidence": [],
            "reviewedTopology": {"regions": [
                {"slot": "merchant_head", "coord": [24, 520, 180, 180]},
                {"slot": "merchant_info", "coord": [220, 520, 700, 180]},
                {"slot": "attached_goods", "coord": [220, 720, 900, 240]},
            ], "attachedItems": [{"itemIndex": 1, "coord": [220, 720, 180, 240], "visibleStatus": "confirmed"}]},
        }
        features = extract_features(card, facts, {})
        self.assertTrue(features["merchant_graphic_boundary"])
        self.assertTrue(features["graphic_downhang"])

    def test_naturally_cropped_downhang_item_does_not_become_uncertain(self):
        elements = [
            {"id": "P1", "元素类型": "图片", "坐标": [100, 200, 120, 120], "render": {"visibleStatus": "naturally_cropped"}},
            {"id": "T1", "元素类型": "文本", "坐标": [100, 330, 120, 30], "render": {"visibleStatus": "naturally_cropped"}, "textFacts": {"semanticRole": "title"}},
            {"id": "T2", "元素类型": "文本", "坐标": [100, 365, 100, 30], "render": {"visibleStatus": "naturally_cropped"}, "textFacts": {"semanticRole": "price"}},
        ]
        groups = append_item_groups("下挂商品区", elements, "商家卡片_图文下挂")
        self.assertEqual(groups[0]["visibleStatus"], "naturally_cropped")

    def test_declared_item_ownership_wins_over_nearest_image_geometry(self):
        elements = [
            {"id": "P1", "元素类型": "图片", "坐标": [100, 200, 120, 120], "render": {"visibleStatus": "confirmed"}, "_reviewItemIndex": 1},
            {"id": "P2", "元素类型": "图片", "坐标": [300, 200, 120, 120], "render": {"visibleStatus": "confirmed"}, "_reviewItemIndex": 2},
            # This label sits nearer to P1 but the current-pixel review saw it
            # as the title of item 2; grouping must preserve that ownership.
            {"id": "T2", "元素类型": "文本", "坐标": [205, 330, 90, 30], "render": {"visibleStatus": "confirmed"}, "textFacts": {"semanticRole": "title"}, "_reviewItemIndex": 2},
        ]
        groups = append_item_groups("下挂商品区", elements, "商家卡片_图文下挂")
        self.assertIn("T2", groups[1]["elementIds"])

    def test_paddle_mode_cannot_be_reenabled_through_the_python_api(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "cv_llm only"):
                run("x", Path(temp) / "screen.png", Path(temp) / "elements.json", None, Path(temp) / "artifacts", recognition_mode="paddle_assisted")

    def test_complete_review_requires_registered_type_and_topology(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "review.json"
            path.write_text(json.dumps({"completeCurrentPixelReview": True, "cards": [{"cardId": "C1", "cardTypeCandidate": "商家卡片_图文下挂", "topology": {"regions": []}}]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "topology regions"):
                validate_cv_llm_visual_review(path)
