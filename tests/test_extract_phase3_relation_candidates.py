from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "phase3-evaluation-officer" / "scripts" / "extract_phase3_relation_candidates.py"


def load_module():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("extract_phase3_relation_candidates_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def item(element_id: str, text: str, role: str, element_type: str = "文本") -> dict:
    return {
        "id": element_id, "元素类型": element_type, "内容简述": f"原文:{text}", "坐标": [0, 0, 10, 10],
        "isExcluded": False, "render": {"visibleStatus": "confirmed"},
        "visual": {"visualStatus": "confirmed"}, "textFacts": {"rawText": text, "semanticRole": role},
    }


class ExtractPhase3RelationCandidatesTest(unittest.TestCase):
    def test_phase3_enumerates_pairs_without_phase2_relation_results(self) -> None:
        module = load_module()
        manifest = {"query": "q", "relations": [], "cards": [{
            "cardId": "C1", "regions": [
                {"name": "标题区", "elements": [item("T", "门店A", "title"), item("A", "可退", "benefit")]},
                {"name": "下挂商品区", "elements": [item("I", "", "image", "图片"), item("B", "可退", "benefit")]},
            ],
        }]}
        result = module.derive_relation_candidates(manifest)
        self.assertEqual(len(result["authenticityCandidates"][0]["candidatePairs"]), 2)
        pairs = result["redundancyCandidates"][0]["candidatePairs"]
        self.assertTrue(any({pair["left"]["elementId"], pair["right"]["elementId"]} == {"A", "B"} for pair in pairs))
        self.assertTrue(all(pair["phase3JudgementRequired"] for pair in pairs))

    def test_title_size_is_an_authenticity_candidate(self) -> None:
        module = load_module()
        manifest = {"query": "安睡裤", "cards": [{
            "cardId": "C3", "regions": [
                {"name": "标题区", "elements": [item("T", "安睡裤M-L码", "title")]},
                {"name": "基础信息区", "elements": [item("S", "M", "size")]},
            ],
        }]}
        result = module.derive_relation_candidates(manifest)
        pairs = result["authenticityCandidates"][0]["candidatePairs"]
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["relationType"], "title_to_size")
        self.assertEqual(pairs[0]["target"]["elementId"], "S")

    def test_range_cap_and_mixed_price_semantics_are_authenticity_candidates(self) -> None:
        module = load_module()
        manifest = {"query": "榴莲", "cards": [{
            "cardId": "C2", "regions": [
                {"name": "标题区", "elements": [item("T", "金枕榴莲3-6斤", "title")]},
                {"name": "基础信息区", "elements": [item("B", "约2kg以下", "other")]},
                {"name": "价格区", "elements": [item("P", "¥24.9起 到手价/每瓶¥4.15", "price")]},
            ],
        }]}
        result = module.derive_relation_candidates(manifest)
        authenticity = result["authenticityCandidates"][0]
        self.assertTrue(any(pair["target"]["elementId"] == "B" for pair in authenticity["candidatePairs"]))
        cues = {candidate["lexicalCue"] for candidate in authenticity["internalCandidates"]}
        self.assertIn("quantity_range_exceeds_card_cap", cues)
        self.assertIn("start_price_and_to_hand_price_in_same_claim", cues)

    def test_title_self_repeat_is_retained_for_redundancy_review(self) -> None:
        module = load_module()
        manifest = {"query": "榴莲", "cards": [{
            "cardId": "C3", "regions": [
                {"name": "标题区", "elements": [item("T", "榴莲3-4斤 金枕榴莲3-4斤", "title")]},
            ],
        }]}
        result = module.derive_relation_candidates(manifest)
        repeats = result["redundancyCandidates"][0]["selfRepeatCandidates"]
        self.assertEqual(repeats[0]["repeatedFragment"], "3-4斤")
        self.assertEqual(repeats[0]["occurrences"], 2)


if __name__ == "__main__":
    unittest.main()
