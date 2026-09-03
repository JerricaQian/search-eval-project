import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "phase2-card-annotation" / "scripts")
sys.path.insert(0, SCRIPTS)

from apply_visual_review import apply  # noqa: E402
from build_phase2_manifest import append_item_groups  # noqa: E402
from build_search_result_candidates import _repeated_merchant_head_cards  # noqa: E402
from card_contract_engine import extract_features  # noqa: E402
from card_type_registry import load_registry, validate_phase2_taxonomy  # noqa: E402
from run_phase2_recognition import merge_reviewed_card_boundaries, run, validate_cv_llm_visual_review  # noqa: E402
from validate_phase2_recognition import gate  # noqa: E402

sys.path.remove(SCRIPTS)


class CvLlmTopologyTests(unittest.TestCase):
    def test_merchant_candidate_does_not_claim_graphic_downhang_without_attached_photo(self):
        facts = {
            "viewport": {"width": 400, "height": 600},
            "candidates": {"photos": [
                {"id": "H1", "coord": [10, 100, 100, 100], "route": "accepted"},
                {"id": "H2", "coord": [10, 350, 100, 100], "route": "accepted"},
            ]},
        }
        cards = _repeated_merchant_head_cards(facts, [], 50)
        self.assertEqual(len(cards), 2)
        self.assertTrue(all(not card["attachedProductPhotoIds"] for card in cards))
        self.assertTrue(all("right_side_attached_product_image_group" not in card["evidence"] for card in cards))
        self.assertTrue(all("summary_and_product_rail_owned_together" not in card["evidence"] for card in cards))

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

    def test_reviewed_text_downhang_overrides_stale_graphic_hint(self):
        facts = {
            "viewport": {"width": 1206, "height": 2622},
            "candidates": {
                "text": [{"coord": [286, 1080, 700, 40], "text": "第一防护·专业运动拉伸馆", "route": "accepted"}],
                "photos": [{"coord": [30, 1080, 228, 228], "route": "accepted"}],
            },
        }
        card = {
            "coord": [0, 1040, 1206, 380],
            "status": "confirmed",
            "evidence": ["repeated_left_image_right_text_seed", "right_side_attached_product_image_group"],
            "reviewedTopology": {
                "regions": [
                    {"slot": "merchant_head", "coord": [30, 1080, 228, 228]},
                    {"slot": "merchant_info", "coord": [286, 1080, 890, 120]},
                    {"slot": "text_attachment", "coord": [286, 1210, 890, 120]},
                ],
                "attachedItems": [
                    {"itemIndex": 1, "coord": [286, 1210, 890, 44], "visibleStatus": "confirmed"},
                    {"itemIndex": 2, "coord": [286, 1270, 890, 44], "visibleStatus": "confirmed"},
                ],
            },
        }
        features = extract_features(card, facts, {})
        self.assertTrue(features["text_downhang"])
        self.assertTrue(features["merchant_text_boundary"])
        self.assertFalse(features["graphic_downhang"])
        self.assertFalse(features["merchant_graphic_boundary"])

    def test_review_merge_removes_stale_graphic_ownership_for_text_downhang(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            candidates_path = temp_path / "candidates.json"
            facts_path = temp_path / "facts.json"
            review_path = temp_path / "review.json"
            candidates_path.write_text(json.dumps({"resultCards": [{
                "id": "C1", "coord": [0, 100, 400, 300], "status": "confirmed",
                "attachedProductPhotoIds": ["OLD"],
                "evidence": ["left_square_merchant_head", "right_side_attached_product_image_group", "summary_and_product_rail_owned_together"],
            }]}), encoding="utf-8")
            facts_path.write_text(json.dumps({"candidates": {"photos": []}}), encoding="utf-8")
            review_path.write_text(json.dumps({"cards": [{
                "cardId": "C1", "coord": [0, 100, 400, 300], "cardTypeCandidate": "商家卡片_文字下挂",
                "topology": {"regions": [
                    {"slot": "merchant_head", "coord": [10, 110, 100, 100]},
                    {"slot": "merchant_info", "coord": [130, 110, 250, 80]},
                    {"slot": "text_attachment", "coord": [130, 210, 250, 120]},
                ], "attachedItems": [{"itemIndex": 1, "coord": [130, 210, 250, 50]}]},
            }]}), encoding="utf-8")
            merge_reviewed_card_boundaries(candidates_path, review_path, facts_path)
            card = json.loads(candidates_path.read_text(encoding="utf-8"))["resultCards"][0]
        self.assertNotIn("attachedProductPhotoIds", card)
        self.assertNotIn("right_side_attached_product_image_group", card["evidence"])
        self.assertNotIn("summary_and_product_rail_owned_together", card["evidence"])
        self.assertEqual(card["classificationHint"]["cardType"], "商家卡片_文字下挂")

    def test_review_merge_reconciles_duplicate_cv_candidate_and_adjacent_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            candidates_path = temp_path / "candidates.json"
            facts_path = temp_path / "facts.json"
            review_path = temp_path / "review.json"
            candidates_path.write_text(json.dumps({"resultCards": [
                {"id": "C1", "coord": [0, 100, 400, 430], "status": "confirmed"},
                {"id": "C2", "coord": [0, 115, 400, 385], "status": "confirmed", "confidence": 0.49},
                {"id": "C3", "coord": [0, 500, 400, 300], "status": "confirmed"},
            ]}), encoding="utf-8")
            facts_path.write_text(json.dumps({"candidates": {"photos": []}}), encoding="utf-8")
            review_path.write_text(json.dumps({"cards": [
                {"cardId": "C1", "coord": [0, 100, 400, 430], "cardTypeCandidate": "商品卡片",
                 "topology": {"regions": [{"slot": "head_media", "coord": [20, 100, 100, 100]}, {"slot": "price", "coord": [140, 400, 180, 100]}], "attachedItems": []}},
                {"cardId": "C3", "coord": [0, 500, 400, 300], "cardTypeCandidate": "商品卡片",
                 "topology": {"regions": [{"slot": "head_media", "coord": [20, 500, 100, 100]}, {"slot": "price", "coord": [140, 650, 180, 80]}], "attachedItems": []}},
            ]}), encoding="utf-8")

            merge_reviewed_card_boundaries(candidates_path, review_path, facts_path)
            cards = json.loads(candidates_path.read_text(encoding="utf-8"))["resultCards"]
            reconciliation = json.loads((temp_path / "candidates.review-reconciliation.json").read_text(encoding="utf-8"))

        self.assertEqual([card["id"] for card in cards], ["C1", "C3"])
        self.assertEqual(cards[0]["coord"], [0, 100, 400, 400])
        self.assertIn("clip_reviewed_card_tail", [item["action"] for item in reconciliation["actions"]])
        self.assertIn("suppress_unreviewed_contained_candidate", [item["action"] for item in reconciliation["actions"]])

    def test_bottom_cropped_graphic_card_review_can_omit_unseen_downhang(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            screenshot = temp_path / "screen.png"
            Image.new("RGB", (400, 600), "white").save(screenshot)
            review_path = temp_path / "review.json"
            review_path.write_text(json.dumps({
                "screenshot": str(screenshot), "completeCurrentPixelReview": True,
                "cards": [{
                    "cardId": "C2", "coord": [0, 510, 400, 90], "cardTypeCandidate": "商家卡片_图文下挂",
                    "topology": {"regions": [{"slot": "merchant_head", "coord": [10, 520, 70, 70]}], "attachedItems": []},
                }],
            }), encoding="utf-8")
            validate_cv_llm_visual_review(review_path)

    def test_reviewed_topology_conflict_blocks_only_complete_card(self):
        facts = {"candidates": {"text": [
            {"id": "T1", "text": "测试商家", "coord": [130, 110, 160, 24], "route": "accepted"},
            {"id": "T2", "text": "4.5分", "coord": [130, 145, 80, 24], "route": "accepted"},
        ]}}
        candidate = {
            "id": "C1", "coord": [0, 100, 400, 300], "status": "confirmed",
            "reviewedTopology": {"regions": [
                {"slot": "merchant_head", "coord": [10, 110, 100, 100]},
                {"slot": "merchant_info", "coord": [130, 110, 250, 80]},
                {"slot": "text_attachment", "coord": [130, 210, 250, 120]},
            ], "attachedItems": [{"itemIndex": 1, "coord": [130, 210, 250, 50]}]},
        }
        semantics = {"cardId": "C1", "selectedCardType": {"cardType": "异构卡", "status": "confirmed"},
                     "contractValidation": {"minimumSatisfied": True}, "regions": []}
        text_semantics = {"candidates": [
            {"sourceId": "T1", "semanticRoleCandidate": "title", "status": "confirmed"},
            {"sourceId": "T2", "semanticRoleCandidate": "rating", "status": "confirmed"},
        ]}
        complete = gate(facts, {"resultCards": [candidate]}, {"cards": [semantics]}, text_semantics)
        self.assertIn("C1:reviewed_topology_selected_card_type_conflict", complete["errors"])
        partial_semantics = {**semantics, "partialCardPolicy": {"applied": True}}
        partial = gate(facts, {"resultCards": [candidate]}, {"cards": [partial_semantics]}, text_semantics)
        self.assertNotIn("C1:reviewed_topology_selected_card_type_conflict", partial["errors"])

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
