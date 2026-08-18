from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "phase2-card-annotation/scripts/extract_cv_facts.py"
PHOTO_SCRIPT = PROJECT_DIR / "phase2-card-annotation/scripts/detect_photo_region.py"
STRUCTURE_SCRIPT = PROJECT_DIR / "phase2-card-annotation/scripts/build_search_page_structure.py"
SEMANTIC_SCRIPT = PROJECT_DIR / "phase2-card-annotation/scripts/map_search_page_semantics.py"
RESULT_CANDIDATES_SCRIPT = PROJECT_DIR / "phase2-card-annotation/scripts/build_search_result_candidates.py"
RESULT_SEMANTICS_SCRIPT = PROJECT_DIR / "phase2-card-annotation/scripts/map_result_card_semantics.py"
MANIFEST_SCRIPT = PROJECT_DIR / "phase2-card-annotation/scripts/build_phase2_manifest.py"
MANIFEST_VALIDATOR = PROJECT_DIR / "scripts/validate_element_manifest.py"
RECOGNITION_GATE = PROJECT_DIR / "phase2-card-annotation/scripts/validate_phase2_recognition.py"
GOLDEN_PAGE_STRUCTURE = PROJECT_DIR / "phase2-card-annotation/references/golden_page_structure.v1.json"
GOLDEN_PRODUCT_PAGE_STRUCTURE = PROJECT_DIR / "phase2-card-annotation/references/golden_product_page_structure.v1.json"
RECOGNITION_CONTRACTS = PROJECT_DIR / "phase2-card-annotation/references/card_recognition_contracts.v1.json"


class ExtractCvFactsTest(unittest.TestCase):
    def test_low_hue_textured_product_photo_is_not_discarded_as_ui(self) -> None:
        script_dir = PHOTO_SCRIPT.parent
        sys.path.insert(0, str(script_dir))
        try:
            spec = importlib.util.spec_from_file_location("phase2_detect_photo_region_test", PHOTO_SCRIPT)
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        stats = {"active_bins": 2, "rgb_std": 79.0, "chrom_ratio": 0.61, "hue_std": 3.0}
        self.assertEqual(module._classify(58, 1166, 278, 222, 42534, stats), ("photo", "low_hue_textured"))
        flat = {"active_bins": 2, "rgb_std": 20.0, "chrom_ratio": 0.9, "hue_std": 2.0}
        self.assertNotEqual(module._classify(58, 1166, 278, 222, 42534, flat)[0], "photo")

    def test_bounded_price_refinement_requires_numeric_anchor(self) -> None:
        script_dir = SCRIPT.parent
        sys.path.insert(0, str(script_dir))
        try:
            spec = importlib.util.spec_from_file_location("phase2_extract_cv_facts_test", SCRIPT)
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        self.assertEqual(
            module._select_bounded_price_refinement("em 10.9神价 每片2.18", [{"text": "¥10.9 神价/每片Y2.18"}]),
            "¥10.9 神价/每片Y2.18",
        )
        self.assertEqual(module._select_bounded_price_refinement("起送#35免配送费", [{"text": "¥20"}]), "")
        entries = [{"text": "Lee¥21.7言方ih", "ocrConsensus": {"status": "disagreed", "secondaryText": "¥21.7官方补贴已售5000+"}}]
        self.assertEqual(module._prefer_independent_structured_text(entries), 1)
        self.assertEqual(entries[0]["text"], "¥21.7官方补贴已售5000+")
        mismatch = [{"text": "Y¥97.5起", "ocrConsensus": {"status": "disagreed", "secondaryText": "¥37.5起"}}]
        self.assertEqual(module._prefer_independent_structured_text(mismatch), 0)

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

    def test_product_quantity_and_price_confirm_product_card_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            facts_path = tmp_path / "facts.json"
            output_path = tmp_path / "classification.json"
            facts_path.write_text(json.dumps({
                "contractVersion": "phase2.cv-facts.v1", "screenshot": "/tmp/screen.png",
                "candidates": {"text": [
                    {"id": "T1", "text": "布洛芬咀嚼片 0.2g*10片", "coord": [220, 300, 280, 36]},
                    {"id": "T2", "text": "¥22.4", "coord": [220, 390, 90, 36]},
                ]},
            }, ensure_ascii=False), encoding="utf-8")
            subprocess.run(
                [sys.executable, str(PROJECT_DIR / "phase2-card-annotation/scripts/classify_search_card_types.py"),
                 str(facts_path), "--taxonomy", str(PROJECT_DIR / "phase2-card-annotation/references/search_card_taxonomy.v1.json"),
                 "--coord", "0,200,600,400", "--output", str(output_path)],
                check=True, cwd=PROJECT_DIR, capture_output=True, text=True,
            )
            result = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result["selected"]["cardType"], "商品卡片")
        self.assertEqual(result["selected"]["status"], "confirmed")

    def test_contract_state_machine_uses_known_then_ad_then_heterogeneous(self) -> None:
        cases = [
            ("known", [{"id": "P1", "coord": [20, 100, 100, 100], "route": "accepted"}], [
                {"id": "T1", "text": "布洛芬咀嚼片", "coord": [150, 100, 150, 28], "route": "accepted"},
                {"id": "T2", "text": "¥20", "coord": [150, 150, 70, 28], "route": "accepted"},
            ], "商品卡片"),
            ("advertising", [], [{"id": "T1", "text": "广告 品牌活动", "coord": [40, 100, 180, 30], "route": "accepted"}], "广告卡"),
            ("heterogeneous", [], [{"id": "T1", "text": "直播专题入口", "coord": [40, 100, 180, 30], "route": "accepted"}], "异构卡"),
        ]
        for name, photos, texts, expected in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                facts_path, candidates_path, output_path = tmp_path / "facts.json", tmp_path / "candidates.json", tmp_path / "semantics.json"
                facts_path.write_text(json.dumps({
                    "contractVersion": "phase2.cv-facts.v1", "screenshot": "/tmp/screen.png", "viewport": {"width": 320, "height": 320},
                    "candidates": {"photos": photos, "text": texts}, "routing": {"missingCapabilities": []},
                }, ensure_ascii=False), encoding="utf-8")
                candidates_path.write_text(json.dumps({
                    "contractVersion": "phase2.search-result-candidates.v1", "resultCards": [{"id": "C1", "coord": [0, 80, 320, 200], "status": "confirmed", "memberBlockIds": [], "evidence": ["repeated_left_image_right_text_seed"]}], "structureBlocks": []
                }, ensure_ascii=False), encoding="utf-8")
                subprocess.run([sys.executable, str(RESULT_SEMANTICS_SCRIPT), str(facts_path), str(candidates_path), "--output", str(output_path)], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)
                result = json.loads(output_path.read_text(encoding="utf-8"))["cards"][0]

            self.assertEqual(result["selectedCardType"]["cardType"], expected)
            self.assertEqual(result["selectedCardType"]["status"], "confirmed")
            self.assertTrue(result["contractValidation"]["minimumSatisfied"])
            self.assertNotEqual(result["selectedCardType"]["cardType"], "unknown")

    def test_learned_geometry_is_a_soft_known_type_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            facts_path, candidates_path, output_path = tmp_path / "facts.json", tmp_path / "candidates.json", tmp_path / "semantics.json"
            facts_path.write_text(json.dumps({
                "contractVersion": "phase2.cv-facts.v1", "screenshot": "/tmp/screen.png", "viewport": {"width": 400, "height": 900},
                "candidates": {
                    "photos": [{"id": "P1", "coord": [20, 200, 120, 120], "route": "accepted"}],
                    "text": [
                        {"id": "T1", "text": "布洛芬咀嚼片", "coord": [160, 200, 170, 28], "route": "accepted"},
                        {"id": "T2", "text": "¥20", "coord": [160, 280, 70, 28], "route": "accepted"},
                    ],
                }, "routing": {"missingCapabilities": []},
            }, ensure_ascii=False), encoding="utf-8")
            candidates_path.write_text(json.dumps({
                "contractVersion": "phase2.search-result-candidates.v1",
                "resultCards": [{"id": "C1", "coord": [0, 180, 400, 180], "status": "confirmed", "memberBlockIds": [], "evidence": ["repeated_left_image_right_text_seed"]}],
                "structureBlocks": [],
            }, ensure_ascii=False), encoding="utf-8")
            subprocess.run([sys.executable, str(RESULT_SEMANTICS_SCRIPT), str(facts_path), str(candidates_path), "--output", str(output_path)], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)
            card = json.loads(output_path.read_text(encoding="utf-8"))["cards"][0]

        self.assertEqual(card["selectedCardType"]["cardType"], "商品卡片")
        geometry = card["contractValidation"]["geometryValidation"]
        self.assertTrue(geometry["available"])
        self.assertTrue(geometry["withinLearnedRange"])
        self.assertEqual(geometry["source"], "approved_golden_aggregate_geometry")

    def test_bottom_partial_merchant_card_inherits_previous_type_and_waives_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            facts_path, candidates_path, cards_path, text_path, gate_path = (
                tmp_path / "facts.json", tmp_path / "candidates.json", tmp_path / "cards.json", tmp_path / "text.json", tmp_path / "gate.json"
            )
            facts_path.write_text(json.dumps({
                "contractVersion": "phase2.cv-facts.v1", "screenshot": "/tmp/screen.png", "viewport": {"width": 400, "height": 600},
                "candidates": {
                    "photos": [
                        {"id": "H1", "coord": [20, 110, 110, 110], "route": "accepted"},
                        {"id": "G1", "coord": [160, 230, 120, 100], "route": "accepted"},
                        {"id": "H2", "coord": [20, 520, 80, 80], "route": "accepted"},
                    ],
                    "text": [
                        {"id": "T1", "text": "测试商家", "coord": [150, 120, 120, 24], "route": "accepted", "ocrConsensus": {"status": "confirmed", "primaryText": "测试商家", "secondaryText": "测试商家"}},
                        {"id": "T2", "text": "¥20", "coord": [160, 280, 60, 24], "route": "accepted", "ocrConsensus": {"status": "confirmed", "primaryText": "¥20", "secondaryText": "¥20"}},
                    ],
                }, "routing": {"missingCapabilities": []},
            }, ensure_ascii=False), encoding="utf-8")
            candidates_path.write_text(json.dumps({
                "contractVersion": "phase2.search-result-candidates.v1", "structureBlocks": [],
                "resultCards": [
                    {"id": "C1", "coord": [0, 100, 400, 300], "status": "confirmed", "memberBlockIds": [], "classificationHint": {"cardType": "商家卡片_图文下挂", "confidence": 0.9}, "attachedProductPhotoIds": ["G1"], "evidence": ["left_square_merchant_head", "right_side_attached_product_image_group"]},
                    {"id": "C2", "coord": [0, 500, 400, 100], "status": "confirmed", "memberBlockIds": [], "evidence": ["repeated_left_image_right_text_seed"]},
                ],
            }, ensure_ascii=False), encoding="utf-8")
            subprocess.run([sys.executable, str(RESULT_SEMANTICS_SCRIPT), str(facts_path), str(candidates_path), "--output", str(cards_path)], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)
            cards = json.loads(cards_path.read_text(encoding="utf-8"))
            text_path.write_text(json.dumps({"candidates": [
                {"sourceId": "T1", "semanticRoleCandidate": "title", "status": "confirmed"},
                {"sourceId": "T2", "semanticRoleCandidate": "price", "status": "confirmed"},
            ]}, ensure_ascii=False), encoding="utf-8")
            completed = subprocess.run([sys.executable, str(RECOGNITION_GATE), "--facts", str(facts_path), "--result-candidates", str(candidates_path), "--card-semantics", str(cards_path), "--text-semantics", str(text_path), "--output", str(gate_path)], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)

        partial = cards["cards"][1]
        self.assertEqual(partial["selectedCardType"]["cardType"], "商家卡片_图文下挂")
        self.assertEqual(partial["selectedCardType"]["classificationMode"], "bottom_partial_inherit_previous_merchant_type")
        self.assertTrue(partial["partialCardPolicy"]["applied"])
        self.assertTrue(json.loads(completed.stdout)["valid"])

    def test_price_evidence_recovers_currency_glyph_damage_without_using_delivery_fee(self) -> None:
        cases = [("YQ97.5起", "red", "商品卡片"), ("起送#35免配送费", "red", "异构卡")]
        for price_text, color, expected in cases:
            with self.subTest(text=price_text), tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                facts_path, candidates_path, output_path = tmp_path / "facts.json", tmp_path / "candidates.json", tmp_path / "cards.json"
                facts_path.write_text(json.dumps({
                    "contractVersion": "phase2.cv-facts.v1", "screenshot": "/tmp/screen.png", "viewport": {"width": 400, "height": 600},
                    "candidates": {
                        "photos": [{"id": "P1", "coord": [20, 120, 110, 110], "route": "accepted"}],
                        "text": [
                            {"id": "T1", "text": "测试商品", "coord": [150, 120, 120, 24], "route": "accepted", "visualHint": {"colorRole": "neutral"}},
                            {"id": "T2", "text": price_text, "coord": [155, 220, 130, 32], "route": "accepted", "visualHint": {"colorRole": color}},
                        ],
                    }, "routing": {"missingCapabilities": []},
                }, ensure_ascii=False), encoding="utf-8")
                candidates_path.write_text(json.dumps({
                    "contractVersion": "phase2.search-result-candidates.v1", "structureBlocks": [],
                    "resultCards": [{"id": "C1", "coord": [0, 100, 400, 220], "status": "confirmed", "memberBlockIds": [], "evidence": ["repeated_left_image_right_text_seed"]}],
                }, ensure_ascii=False), encoding="utf-8")
                subprocess.run([sys.executable, str(RESULT_SEMANTICS_SCRIPT), str(facts_path), str(candidates_path), "--output", str(output_path)], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)
                card = json.loads(output_path.read_text(encoding="utf-8"))["cards"][0]

            self.assertEqual(card["selectedCardType"]["cardType"], expected)

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
                    {"id": "T1", "text": "商家标题 4.8分", "coord": [160, 370, 160, 22]}, {"id": "T1a", "text": "可预约服务", "coord": [160, 510, 100, 22]},
                    {"id": "T2", "text": "商家标题 人均¥30", "coord": [160, 690, 180, 22]}, {"id": "T2a", "text": "可预约服务", "coord": [160, 830, 100, 22]},
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
                    {"id": "H1", "coord": [20, 340, 120, 120]}, {"id": "Coupon", "coord": [20, 470, 120, 230]}, {"id": "Goods1", "coord": [150, 480, 110, 160]}, {"id": "Goods2", "coord": [270, 480, 110, 160]}, {"id": "H2", "coord": [20, 700, 120, 120]},
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

    def test_builds_phase3_manifest_with_cv_colour_evidence_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            facts = {
                "screenshot": "/tmp/screen.png", "viewport": {"width": 400, "height": 600},
                "candidates": {"photos": [{"id": "P1", "coord": [20, 120, 120, 120], "route": "accepted"}], "text": [{
                    "id": "T1", "text": "布洛芬咀嚼片", "coord": [160, 130, 180, 28], "route": "accepted",
                    "visualHint": {"colorRole": "red", "medianRgb": [216, 56, 56], "evidence": "foreground_pixel_median"},
                }]}, "routing": {"unresolvedCandidateIds": []},
            }
            candidates = {"pageModules": [{"module": "results_list", "coord": [0, 100, 400, 200], "status": "confirmed", "evidence": ["result_cards"]}], "resultCards": [{"id": "C1", "coord": [0, 100, 400, 200]}]}
            card_semantics = {"cards": [{"cardId": "C1", "selectedCardType": {"cardType": "商品卡片", "status": "confirmed", "evidence": ["quantity_and_price"]}, "regions": []}]}
            text_semantics = {"candidates": [{"sourceId": "T1", "semanticRoleCandidate": "title", "regionCandidate": "标题区", "status": "confirmed"}]}
            paths = {name: tmp_path / f"{name}.json" for name in ("facts", "candidates", "cards", "text", "elements", "recognition")}
            for name, payload in (("facts", facts), ("candidates", candidates), ("cards", card_semantics), ("text", text_semantics)):
                paths[name].write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            subprocess.run([sys.executable, str(MANIFEST_SCRIPT), "--query", "布洛芬", "--facts", str(paths["facts"]), "--result-candidates", str(paths["candidates"]), "--card-semantics", str(paths["cards"]), "--text-semantics", str(paths["text"]), "--output", str(paths["elements"]), "--recognition-audit", str(paths["recognition"])], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)
            validation = subprocess.run([sys.executable, str(MANIFEST_VALIDATOR), str(paths["elements"]), "--recognition-audit", str(paths["recognition"])], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)
            manifest = json.loads(paths["elements"].read_text(encoding="utf-8"))

        element = manifest["cards"][0]["regions"][0]["elements"][0]
        self.assertEqual(element["visual"]["colorRole"], "red")
        self.assertEqual(element["visual"]["textColor"], "#D83838")
        self.assertIn("foreground_pixel_median", element["visual"]["colorEvidence"])
        self.assertTrue(json.loads(validation.stdout)["valid"])

    def test_recognition_gate_blocks_by_batch_quality_not_ocr_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payloads = {
                "facts": {"candidates": {"text": [{"id": "T1", "text": "布洛芬", "coord": [160, 120, 80, 24], "route": "accepted", "ocrConsensus": {"status": "confirmed", "primaryText": "布洛芬", "secondaryText": "布洛芬"}}, {"id": "T2", "text": "¥20", "coord": [160, 160, 60, 24], "route": "accepted", "ocrConsensus": {"status": "confirmed", "primaryText": "¥20", "secondaryText": "¥20"}}], "photos": [{"id": "P1", "coord": [20, 100, 100, 100], "route": "accepted"}]}},
                "candidates": {"resultCards": [{"id": "C1", "coord": [0, 80, 320, 200]}]},
                "cards": {"cards": [{"cardId": "C1", "selectedCardType": {"cardType": "商品卡片", "status": "confirmed"}}]},
                "text": {"candidates": [
                    {"sourceId": "T1", "text": "布洛芬", "semanticRoleCandidate": "title", "status": "confirmed"},
                    {"sourceId": "T2", "text": "¥20", "semanticRoleCandidate": "price", "status": "confirmed"},
                ]},
            }
            paths = {name: tmp_path / f"{name}.json" for name in payloads}
            for name, content in payloads.items():
                paths[name].write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
            report = tmp_path / "gate.json"
            completed = subprocess.run([sys.executable, str(RECOGNITION_GATE), "--facts", str(paths["facts"]), "--result-candidates", str(paths["candidates"]), "--card-semantics", str(paths["cards"]), "--text-semantics", str(paths["text"]), "--output", str(report)], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)

        self.assertTrue(json.loads(completed.stdout)["valid"])

    def test_recognition_gate_blocks_fluent_looking_text_when_ocr_layouts_disagree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payloads = {
                "facts": {"candidates": {"text": [
                    {"id": "T1", "text": "仁辣共去", "coord": [160, 120, 100, 24], "route": "accepted", "ocrConsensus": {"status": "disagreed", "primaryText": "仁辣共去", "secondaryText": "人来公园"}},
                    {"id": "T2", "text": "¥20", "coord": [160, 160, 60, 24], "route": "accepted", "ocrConsensus": {"status": "confirmed", "primaryText": "¥20", "secondaryText": "¥20"}},
                ], "photos": [{"id": "P1", "coord": [20, 100, 100, 100], "route": "accepted"}]}},
                "candidates": {"resultCards": [{"id": "C1", "coord": [0, 80, 320, 200]}]},
                "cards": {"cards": [{"cardId": "C1", "selectedCardType": {"cardType": "商品卡片", "status": "confirmed"}}]},
                "text": {"candidates": [
                    {"sourceId": "T1", "text": "仁辣共去", "semanticRoleCandidate": "title", "status": "confirmed"},
                    {"sourceId": "T2", "text": "¥20", "semanticRoleCandidate": "price", "status": "confirmed"},
                ]},
            }
            paths = {name: tmp_path / f"{name}.json" for name in payloads}
            for name, content in payloads.items():
                paths[name].write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
            report = tmp_path / "gate.json"
            completed = subprocess.run([sys.executable, str(RECOGNITION_GATE), "--facts", str(paths["facts"]), "--result-candidates", str(paths["candidates"]), "--card-semantics", str(paths["cards"]), "--text-semantics", str(paths["text"]), "--output", str(report)], check=False, cwd=PROJECT_DIR, capture_output=True, text=True)

        result = json.loads(completed.stdout)
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(result["valid"])
        self.assertTrue(any(item["hook"] == "ocr_consensus" and item["sourceId"] == "T1" for item in result["semanticHookFindings"]))

    def test_recognition_gate_reuses_confirmed_card_region_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payloads = {
                "facts": {"candidates": {"text": [
                    {"id": "T1", "text": "布洛芬咀嚼片", "coord": [160, 120, 120, 24], "route": "accepted", "ocrConsensus": {"status": "confirmed", "primaryText": "布洛芬咀嚼片", "secondaryText": "布洛芬咀嚼片"}},
                    {"id": "T2", "text": "¥20", "coord": [160, 160, 60, 24], "route": "accepted", "ocrConsensus": {"status": "confirmed", "primaryText": "¥20", "secondaryText": "¥20"}},
                ], "photos": [{"id": "P1", "coord": [20, 100, 100, 100], "route": "accepted"}]}},
                "candidates": {"resultCards": [{"id": "C1", "coord": [0, 80, 320, 200]}]},
                "cards": {"cards": [{
                    "cardId": "C1", "selectedCardType": {"cardType": "商品卡片", "status": "confirmed"},
                    "contractValidation": {"minimumSatisfied": True},
                    "regions": [
                        {"region": "标题区", "status": "confirmed", "evidenceSourceIds": ["T1"]},
                        {"region": "价格区", "status": "confirmed", "evidenceSourceIds": ["T2"]},
                    ],
                }]},
                "text": {"candidates": []},
            }
            paths = {name: tmp_path / f"{name}.json" for name in payloads}
            for name, content in payloads.items():
                paths[name].write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
            report = tmp_path / "gate.json"
            completed = subprocess.run([sys.executable, str(RECOGNITION_GATE), "--facts", str(paths["facts"]), "--result-candidates", str(paths["candidates"]), "--card-semantics", str(paths["cards"]), "--text-semantics", str(paths["text"]), "--output", str(report)], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)

        self.assertTrue(json.loads(completed.stdout)["valid"])

    def test_consensus_hook_accepts_compatible_title_crop_but_not_rewritten_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payloads = {
                "facts": {"candidates": {"text": [
                    {"id": "T1", "text": "锦州烧烤望京店", "coord": [160, 120, 130, 24], "route": "accepted", "ocrConsensus": {"status": "disagreed", "primaryText": "锦州烧烤望京店", "secondaryText": "锦州烧烤望京"}},
                    {"id": "T2", "text": "¥20", "coord": [160, 160, 60, 24], "route": "accepted", "ocrConsensus": {"status": "confirmed", "primaryText": "¥20", "secondaryText": "¥20"}},
                ], "photos": [{"id": "P1", "coord": [20, 100, 100, 100], "route": "accepted"}]}},
                "candidates": {"resultCards": [{"id": "C1", "coord": [0, 80, 320, 200]}]},
                "cards": {"cards": [{"cardId": "C1", "selectedCardType": {"cardType": "商品卡片", "status": "confirmed"}, "contractValidation": {"minimumSatisfied": True}}]},
                "text": {"candidates": [
                    {"sourceId": "T1", "semanticRoleCandidate": "title", "status": "confirmed"},
                    {"sourceId": "T2", "semanticRoleCandidate": "price", "status": "confirmed"},
                ]},
            }
            paths = {name: tmp_path / f"{name}.json" for name in payloads}
            for name, content in payloads.items():
                paths[name].write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
            report = tmp_path / "gate.json"
            completed = subprocess.run([sys.executable, str(RECOGNITION_GATE), "--facts", str(paths["facts"]), "--result-candidates", str(paths["candidates"]), "--card-semantics", str(paths["cards"]), "--text-semantics", str(paths["text"]), "--output", str(report)], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)

        result = json.loads(completed.stdout)
        self.assertTrue(result["valid"])
        self.assertEqual(payloads["facts"]["candidates"]["text"][0]["text"], "锦州烧烤望京店")

    def test_blocked_gate_is_embedded_in_single_manifest_and_blocks_phase3(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payloads = {
                "facts": {"screenshot": "/tmp/screen.png", "viewport": {"width": 320, "height": 320}, "backends": {"ocr": "tesseract"}, "routing": {"unresolvedCandidateIds": ["T1"]}, "candidates": {"text": [{"id": "T1", "text": "仁辣共去", "coord": [150, 100, 100, 28], "route": "accepted"}], "photos": [{"id": "P1", "coord": [20, 100, 100, 100], "route": "accepted"}]}},
                "candidates": {"pageModules": [], "resultCards": [{"id": "C1", "coord": [0, 80, 320, 200]}]},
                "cards": {"cards": [{"cardId": "C1", "selectedCardType": {"cardType": "商品卡片", "status": "confirmed", "evidence": ["test"]}, "regions": []}]},
                "text": {"candidates": [{"sourceId": "T1", "semanticRoleCandidate": "title", "regionCandidate": "标题区", "status": "confirmed"}]},
                "gate": {"valid": False, "errors": ["C1:semantic_text_invalid"], "semanticHookFindings": [{"hook": "ocr_consensus", "sourceId": "T1", "reason": "disagreed"}], "reprocessTargets": [{"sourceId": "T1", "hook": "ocr_consensus", "reason": "disagreed", "action": "rerun_bounded_local_ocr_or_rebuild_card_boundary"}], "reprocess": ["rerun C1"]},
            }
            paths = {name: tmp_path / f"{name}.json" for name in payloads}
            for name, payload in payloads.items():
                paths[name].write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            output = tmp_path / "elements.json"
            subprocess.run([sys.executable, str(MANIFEST_SCRIPT), "--query", "测试", "--facts", str(paths["facts"]), "--result-candidates", str(paths["candidates"]), "--card-semantics", str(paths["cards"]), "--text-semantics", str(paths["text"]), "--recognition-gate", str(paths["gate"]), "--output", str(output)], check=True, cwd=PROJECT_DIR, capture_output=True, text=True)
            manifest = json.loads(output.read_text(encoding="utf-8"))
            validated = subprocess.run([sys.executable, str(MANIFEST_VALIDATOR), str(output)], check=False, cwd=PROJECT_DIR, capture_output=True, text=True)
            validation = json.loads(validated.stdout)

        self.assertEqual(manifest["recognition"]["status"], "blocked")
        self.assertFalse(manifest["recognition"]["phase3Ready"])
        self.assertEqual(manifest["recognition"]["blockingCardIds"], ["C1"])
        self.assertNotEqual(validated.returncode, 0)
        self.assertIn("whole_page_recognition_blocked", validation["errors"])


if __name__ == "__main__":
    unittest.main()
