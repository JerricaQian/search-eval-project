from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "phase2-card-annotation/scripts/extract_cv_facts.py"
STRUCTURE_SCRIPT = PROJECT_DIR / "phase2-card-annotation/scripts/build_search_page_structure.py"
SEMANTIC_SCRIPT = PROJECT_DIR / "phase2-card-annotation/scripts/map_search_page_semantics.py"
RESULT_CANDIDATES_SCRIPT = PROJECT_DIR / "phase2-card-annotation/scripts/build_search_result_candidates.py"
RESULT_SEMANTICS_SCRIPT = PROJECT_DIR / "phase2-card-annotation/scripts/map_result_card_semantics.py"
GOLDEN_PAGE_STRUCTURE = PROJECT_DIR / "phase2-card-annotation/references/golden_page_structure.v1.json"
GOLDEN_PRODUCT_PAGE_STRUCTURE = PROJECT_DIR / "phase2-card-annotation/references/golden_product_page_structure.v1.json"


class ExtractCvFactsTest(unittest.TestCase):
    def test_golden_page_contract_lists_complete_ordered_components(self) -> None:
        """Gold annotations, not sparse CV candidates, define page component presence."""
        contract = json.loads(GOLDEN_PAGE_STRUCTURE.read_text(encoding="utf-8"))
        pages = contract["pages"]

        for page_name, components in pages.items():
            types = [item[0] for item in components]
            self.assertEqual(types[0:2], ["search_bar", "tab"], page_name)
            self.assertIn("results_list", types, page_name)
            self.assertGreater(types.count("result_card"), 0, page_name)

        birthday_types = [item[0] for item in pages["商家卡片-图文下挂-搜索词为生日蛋糕"]]
        self.assertEqual(
            birthday_types,
            ["search_bar", "tab", "business_operation_card", "image_filter", "sort_filter", "results_list", "result_card", "result_card"],
        )
        mixue_types = [item[0] for item in pages["商家卡片-图文下挂-搜索词为蜜雪冰城"]]
        self.assertIn("live_card", mixue_types)

        birthday_annotations = contract["componentElementAnnotations"]["商家卡片-图文下挂-搜索词为生日蛋糕"]
        self.assertEqual(birthday_annotations["search_bar"]["searchKeyword"], "生日蛋糕")
        self.assertEqual([item["text"] for item in birthday_annotations["image_filter"]["tabs"]], ["款式", "用途"])
        self.assertEqual([item["text"] for item in birthday_annotations["image_filter"]["items"]], ["动物奶油", "提拉米苏", "慕斯蛋糕", "草莓蛋糕", "榴莲千层", "水果蛋糕"])
        medicine_annotations = contract["componentElementAnnotations"]["商家卡片-图文下挂-搜索词为药店"]
        self.assertEqual([item["text"] for item in medicine_annotations["business_image_filter"]["items"]], ["肠胃用药", "男科用药", "儿童用药", "五官用药", "抗菌消炎", "止痛用药"])

    def test_product_card_golden_contract_preserves_component_ownership(self) -> None:
        contract = json.loads(GOLDEN_PRODUCT_PAGE_STRUCTURE.read_text(encoding="utf-8"))
        self.assertEqual(len(contract["pages"]), 7)
        for page_name, components in contract["pages"].items():
            kinds = [item[0] for item in components]
            self.assertEqual(kinds[:2], ["search_bar", "tab"], page_name)
            self.assertIn("results_list", kinds, page_name)
            self.assertIn("result_card", kinds, page_name)
            self.assertEqual(contract["componentElementAnnotations"][page_name]["searchKeyword"], page_name.removeprefix("商品卡片-搜索词为"))
        ibuprofen = [item[0] for item in contract["pages"]["商品卡片-搜索词为布洛芬"]]
        self.assertIn("heterogeneous_card", ibuprofen)
        self.assertIn("floating_service", ibuprofen)

    def test_golden_outputs_use_page_order_and_result_list_positions(self) -> None:
        for directory in ("merchant-graphic-hang", "product-card"):
            output_dir = PROJECT_DIR / "phase2-card-annotation/golden-sample-results" / directory
            for output_path in output_dir.glob("*.elements.json"):
                result = json.loads(output_path.read_text(encoding="utf-8"))
                components = result["pageStructure"]["components"]
                self.assertEqual([component["order"] for component in components], list(range(1, len(components) + 1)), output_path)
                result_list = next(component for component in components if component["componentType"] == "results_list")
                self.assertEqual([item["listPosition"] for item in result_list["components"]], list(range(1, len(result_list["components"]) + 1)), output_path)

    def test_records_geometry_and_missing_ocr_without_claiming_absence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image_path = tmp_path / "screen.png"
            output_path = tmp_path / "facts.json"
            image = Image.new("RGB", (240, 360), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((12, 80, 228, 170), fill=(30, 30, 30))
            draw.rectangle((12, 210, 228, 290), fill=(80, 120, 190))
            image.save(image_path)

            subprocess.run(
                [sys.executable, str(SCRIPT), str(image_path), "--output", str(output_path)],
                check=True,
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True,
            )
            facts = json.loads(output_path.read_text(encoding="utf-8"))
            structure_path = tmp_path / "structure.json"
            subprocess.run(
                [sys.executable, str(STRUCTURE_SCRIPT), str(output_path), "--output", str(structure_path)],
                check=True,
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True,
            )
            structure = json.loads(structure_path.read_text(encoding="utf-8"))

        self.assertEqual(facts["contractVersion"], "phase2.cv-facts.v1")
        self.assertEqual(facts["viewport"], {"width": 240, "height": 360})
        self.assertGreaterEqual(len(facts["contentRows"]), 2)
        self.assertIn(facts["backends"]["ocr"], {"tesseract", "paddleocr", "unavailable"})
        if facts["backends"]["ocr"] == "unavailable":
            self.assertIn("local_chinese_ocr", facts["routing"]["missingCapabilities"])
        self.assertIn("absence, defects, or excellence", facts["routing"]["rule"])
        self.assertEqual(structure["contractVersion"], "phase2.search-page-structure.v1")
        self.assertGreaterEqual(len(structure["blocks"]), 2)
        self.assertTrue(all(block["route"] == "local_vision" for block in structure["blocks"]))

    def test_maps_colored_live_status_to_a_confirmed_tag_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            facts_path = tmp_path / "facts.json"
            structure_path = tmp_path / "structure.json"
            output_path = tmp_path / "semantic.json"
            facts_path.write_text(json.dumps({
                "contractVersion": "phase2.cv-facts.v1", "screenshot": "/tmp/screen.png",
                "viewport": {"width": 400, "height": 600}, "candidates": {"photos": [], "text": [{
                    "id": "T1", "text": "直播中", "coord": [220, 100, 72, 28], "confidence": 0.97,
                    "visualHint": {"colorRole": "red"},
                }]}, "routing": {"missingCapabilities": []},
            }, ensure_ascii=False), encoding="utf-8")
            structure_path.write_text(json.dumps({
                "contractVersion": "phase2.search-page-structure.v1", "blocks": [{
                    "id": "B1", "coord": [0, 80, 400, 240], "layoutCandidate": "left_image_right_text",
                }],
            }), encoding="utf-8")
            subprocess.run(
                [sys.executable, str(SEMANTIC_SCRIPT), str(facts_path), str(structure_path), "--output", str(output_path)],
                check=True, cwd=PROJECT_DIR, capture_output=True, text=True,
            )
            result = json.loads(output_path.read_text(encoding="utf-8"))

        candidate = result["candidates"][0]
        self.assertEqual(candidate["semanticRoleCandidate"], "tag")
        self.assertEqual(candidate["regionCandidate"], "标签区")
        self.assertEqual(candidate["status"], "confirmed")

    def test_groups_only_post_sort_cards_and_uses_text_attachment_topology(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            facts_path = tmp_path / "facts.json"
            structure_path = tmp_path / "structure.json"
            candidates_path = tmp_path / "candidates.json"
            semantics_path = tmp_path / "semantics.json"
            facts_path.write_text(json.dumps({
                "contractVersion": "phase2.cv-facts.v1", "screenshot": "/tmp/screen.png",
                "viewport": {"width": 400, "height": 1000}, "routing": {"missingCapabilities": []},
                "candidates": {"photos": [
                    {"id": "Pfilter", "coord": [20, 120, 100, 100]}, {"id": "P1", "coord": [20, 360, 120, 120]}, {"id": "P2", "coord": [20, 680, 120, 120]},
                ], "text": [
                    {"id": "Tsort", "text": "综合排序", "coord": [180, 280, 80, 22]},
                    {"id": "T1", "text": "商家标题 ¥20", "coord": [160, 370, 140, 22]}, {"id": "T1a", "text": "服务下挂", "coord": [160, 510, 100, 22]},
                    {"id": "T2", "text": "商家标题 ¥30", "coord": [160, 690, 140, 22]}, {"id": "T2a", "text": "服务下挂", "coord": [160, 830, 100, 22]},
                ]},
            }, ensure_ascii=False), encoding="utf-8")
            structure_path.write_text(json.dumps({
                "contractVersion": "phase2.search-page-structure.v1", "blocks": [
                    {"id": "Bfilter", "coord": [0, 100, 400, 160], "layoutCandidate": "top_image_bottom_text", "confidence": 0.8},
                    {"id": "Bsort", "coord": [0, 260, 400, 80], "layoutCandidate": "text_only", "confidence": 0.8},
                    {"id": "B1", "coord": [0, 340, 400, 140], "layoutCandidate": "left_image_right_text", "confidence": 0.9},
                    {"id": "B1a", "coord": [0, 480, 400, 120], "layoutCandidate": "text_only", "confidence": 0.8},
                    {"id": "B2", "coord": [0, 660, 400, 140], "layoutCandidate": "left_image_right_text", "confidence": 0.9},
                    {"id": "B2a", "coord": [0, 800, 400, 120], "layoutCandidate": "text_only", "confidence": 0.8},
                ],
            }), encoding="utf-8")
            subprocess.run([sys.executable, str(RESULT_CANDIDATES_SCRIPT), str(facts_path), str(structure_path), "--output", str(candidates_path)], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)
            subprocess.run([sys.executable, str(RESULT_SEMANTICS_SCRIPT), str(facts_path), str(candidates_path), "--output", str(semantics_path)], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)
            candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
            semantics = json.loads(semantics_path.read_text(encoding="utf-8"))

        self.assertEqual([card["id"] for card in candidates["resultCards"]], ["C1", "C2"])
        self.assertEqual([card["selectedCardType"]["cardType"] for card in semantics["cards"]], ["商家卡片_文字下挂", "商家卡片_文字下挂"])

    def test_confirms_graphic_hang_from_head_and_right_product_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            facts_path = tmp_path / "facts.json"
            structure_path = tmp_path / "structure.json"
            candidates_path = tmp_path / "candidates.json"
            semantics_path = tmp_path / "semantics.json"
            facts_path.write_text(json.dumps({
                "contractVersion": "phase2.cv-facts.v1", "screenshot": "/tmp/screen.png", "viewport": {"width": 400, "height": 900}, "routing": {"missingCapabilities": []},
                "candidates": {"photos": [
                    {"id": "H1", "coord": [20, 340, 120, 120]}, {"id": "Coupon", "coord": [20, 470, 120, 230]}, {"id": "Goods", "coord": [120, 480, 160, 160]}, {"id": "H2", "coord": [20, 700, 120, 120]},
                ], "text": [
                    {"id": "Sort", "text": "综合排序", "coord": [180, 280, 80, 20]}, {"id": "Title", "text": "商家标题", "coord": [160, 350, 120, 20]}, {"id": "Price", "text": "¥20", "coord": [160, 650, 60, 20]},
                ]},
            }, ensure_ascii=False), encoding="utf-8")
            structure_path.write_text(json.dumps({"contractVersion": "phase2.search-page-structure.v1", "blocks": [
                {"id": "Sort", "coord": [0, 260, 400, 60], "layoutCandidate": "text_only", "confidence": 0.8},
                {"id": "Body", "coord": [0, 320, 400, 150], "layoutCandidate": "left_image_right_text", "confidence": 0.9},
                {"id": "Attach", "coord": [0, 470, 400, 220], "layoutCandidate": "other", "confidence": 0.8},
            ]}), encoding="utf-8")
            subprocess.run([sys.executable, str(RESULT_CANDIDATES_SCRIPT), str(facts_path), str(structure_path), "--output", str(candidates_path)], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)
            subprocess.run([sys.executable, str(RESULT_SEMANTICS_SCRIPT), str(facts_path), str(candidates_path), "--output", str(semantics_path)], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)
            semantics = json.loads(semantics_path.read_text(encoding="utf-8"))

        self.assertEqual(semantics["cards"][0]["selectedCardType"]["cardType"], "商家卡片_图文下挂")
        self.assertEqual(semantics["cards"][0]["selectedCardType"]["status"], "confirmed")


if __name__ == "__main__":
    unittest.main()
