from __future__ import annotations

import json
import importlib.util
import hashlib
import unittest
from pathlib import Path

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = PROJECT_DIR / "scripts" / "validate_element_manifest.py"
TAXONOMY_PATH = PROJECT_DIR / "phase2-card-annotation" / "references" / "search_card_taxonomy.v1.json"
RECOGNITION_CONTRACTS_PATH = PROJECT_DIR / "phase2-card-annotation" / "references" / "card_recognition_contracts.v1.json"
GEOMETRY_PROFILES_PATH = PROJECT_DIR / "phase2-card-annotation" / "references" / "learned_card_geometry_profiles.v1.json"
GOLDEN_PAGE_TRUTH_PATH = PROJECT_DIR / "phase2-card-annotation" / "references" / "golden_page_truth.v2.json"
GOLDEN_ELEMENT_VALIDATOR_PATH = PROJECT_DIR / "phase2-card-annotation" / "scripts" / "validate_golden_element_contract.py"


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_element_manifest", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class JsonArtifactsTest(unittest.TestCase):
    def test_every_committed_json_artifact_parses(self) -> None:
        """Keep static contracts and golden outputs loadable by all consumers."""
        json_paths = sorted(
            path for path in PROJECT_DIR.rglob("*.json")
            if ".git" not in path.parts
        )
        self.assertGreater(len(json_paths), 0)
        for path in json_paths:
            with self.subTest(path=path.relative_to(PROJECT_DIR)):
                json.loads(path.read_text(encoding="utf-8"))

    def test_every_golden_element_output_has_the_page_tree_contract(self) -> None:
        outputs = sorted(
            (PROJECT_DIR / "phase2-card-annotation" / "golden-sample-results").rglob("*.elements.json")
        )
        self.assertGreater(len(outputs), 0)
        for path in outputs:
            with self.subTest(path=path.relative_to(PROJECT_DIR)):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(payload.get("contractVersion"), str)
                self.assertIsInstance(payload.get("pageStructure", {}).get("components"), list)

    def test_every_golden_output_is_annotation_backed_structural_truth(self) -> None:
        outputs = sorted(
            (PROJECT_DIR / "phase2-card-annotation" / "golden-sample-results").rglob("*.elements.json")
        )
        self.assertEqual(len(outputs), 34)
        taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
        allowed_types = {item["id"] for item in taxonomy["cardTypes"]}

        def digest(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest()

        for path in outputs:
            with self.subTest(path=path.relative_to(PROJECT_DIR)):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["contractVersion"], "phase2.golden-structural-truth.v2")
                verification = payload["verification"]
                self.assertEqual(verification["status"], "pixel_verified")
                self.assertIn("runtime_ocr_text", verification["excludedClaims"])
                screenshot = PROJECT_DIR / verification["rawScreenshot"]
                annotation = PROJECT_DIR / verification["componentAnnotation"]
                self.assertEqual(digest(screenshot), verification["rawSha256"])
                self.assertEqual(digest(annotation), verification["componentAnnotationSha256"])
                with Image.open(screenshot) as image:
                    width, height = image.size
                element_count = 0
                stack = [payload]
                while stack:
                    value = stack.pop()
                    if isinstance(value, dict):
                        element_count += int("elementType" in value)
                        stack.extend(value.values())
                    elif isinstance(value, list):
                        stack.extend(value)
                self.assertGreater(element_count, 0, "golden output must retain component elements")
                for component in payload["pageStructure"]["components"]:
                    if component["componentType"] != "results_list":
                        continue
                    for card in component.get("components", []):
                        if card.get("componentType") != "result_card" or "cardType" not in card:
                            continue
                        self.assertIn(card["cardType"], allowed_types)
                        if "coord" not in card:
                            continue
                        self.assertEqual(len(card["coord"]), 4)
                        self.assertIn(card["visibleStatus"], {"complete", "naturally_cropped"})
                        x, y, card_width, card_height = card["coord"]
                        self.assertGreater(card_width, 0)
                        self.assertGreater(card_height, 0)
                        self.assertGreaterEqual(x, 0)
                        self.assertGreaterEqual(y, 0)
                        self.assertLessEqual(x + card_width, width)
                        self.assertLessEqual(y + card_height, height)

    def test_page_truth_index_exactly_mirrors_all_curated_goldens(self) -> None:
        truth = json.loads(GOLDEN_PAGE_TRUTH_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(truth["pages"]), 34)
        outputs = sorted(
            (PROJECT_DIR / "phase2-card-annotation" / "golden-sample-results").rglob("*.elements.json")
        )
        for path in outputs:
            payload = json.loads(path.read_text(encoding="utf-8"))
            screenshot_key = payload["verification"]["rawScreenshot"]
            with self.subTest(path=path.relative_to(PROJECT_DIR)):
                page = truth["pages"][screenshot_key]
                self.assertEqual(page["sourceGolden"], str(path.relative_to(PROJECT_DIR)))
                self.assertIsInstance(page["resultCards"], list)
                self.assertGreater(len(page["resultCards"]), 0)

    def test_golden_page_components_and_result_cards_have_stable_order(self) -> None:
        outputs = sorted(
            (PROJECT_DIR / "phase2-card-annotation" / "golden-sample-results").rglob("*.elements.json")
        )
        for path in outputs:
            with self.subTest(path=path.relative_to(PROJECT_DIR)):
                payload = json.loads(path.read_text(encoding="utf-8"))
                components = payload["pageStructure"]["components"]
                self.assertEqual(
                    [component["order"] for component in components],
                    list(range(1, len(components) + 1)),
                )
                for component in components:
                    if component["componentType"] != "results_list":
                        continue
                    cards = component.get("components", [])
                    self.assertEqual(
                        [card["listPosition"] for card in cards],
                        list(range(1, len(cards) + 1)),
                    )

    def test_primary_point_and_performance_samples_keep_their_card_type_boundaries(self) -> None:
        results = PROJECT_DIR / "phase2-card-annotation" / "golden-sample-results"

        for path in sorted((results / "primary-point-card").glob("*.elements.json")):
            with self.subTest(path=path.relative_to(PROJECT_DIR)):
                components = json.loads(path.read_text(encoding="utf-8"))["pageStructure"]["components"]
                types = [component["componentType"] for component in components]
                self.assertEqual(types[:2], ["search_bar", "tab"])
                self.assertEqual(types.count("primary_point_card"), 1)
                self.assertLess(types.index("primary_point_card"), types.index("results_list"))

        expected_variants = {"演出卡.elements.json": "performance", "电影卡.elements.json": "cinema"}
        for name, variant in expected_variants.items():
            with self.subTest(path=name):
                payload = json.loads((results / "performance-movie-card" / name).read_text(encoding="utf-8"))
                components = payload["pageStructure"]["components"]
                self.assertEqual([component["componentType"] for component in components[:2]], ["search_bar", "tab"])
                result_list = next(component for component in components if component["componentType"] == "results_list")
                self.assertGreater(len(result_list["components"]), 0)
                self.assertTrue(all(card["cardType"] == "演出电影卡片" for card in result_list["components"]))
                self.assertTrue(all(card["variant"] == variant for card in result_list["components"]))

    def test_every_golden_result_card_obeys_shared_element_contract(self) -> None:
        outputs = sorted(
            (PROJECT_DIR / "phase2-card-annotation" / "golden-sample-results").rglob("*.elements.json")
        )

        def nested_elements(value):
            if isinstance(value, dict):
                if "elementType" in value:
                    yield value
                for child in value.values():
                    yield from nested_elements(child)
            elif isinstance(value, list):
                for child in value:
                    yield from nested_elements(child)

        for path in outputs:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for component in payload["pageStructure"]["components"]:
                if component.get("componentType") != "results_list":
                    continue
                for card in component.get("components", []):
                    if card.get("componentType") != "result_card":
                        continue
                    regions = card.get("regions", {})
                    all_elements = list(nested_elements(regions))
                    if card.get("visibleStatus") == "complete" and card.get("cardType") not in {"异构卡", "广告卡"}:
                        titles = [item for item in regions.get("标题区", {}).get("elements", []) if "标题" in str(item.get("elementType", "")) and len("".join(str(item.get("visibleText", "")).split())) >= 2]
                        self.assertTrue(titles, f"{path.name} card {card.get('listPosition')} missing title")
                    for item in all_elements:
                        text = "".join(str(item.get("visibleText", "")).split())
                        self.assertNotEqual(len(text), 1, f"{path.name}: one-character element {text!r}")
                        if item.get("sourceRegion") in {"基础信息区", "商家信息区", "标签区"}:
                            self.assertFalse(any(mark in text for mark in ("｜", "|", "；")), f"{path.name}: merged semantic fields {text!r}")
                    for region_name in ("下挂商品区", "文字下挂区", "下挂区", "服务下挂"):
                        region = regions.get(region_name)
                        if not isinstance(region, dict):
                            continue
                        self.assertEqual(set(region), {"items"}, f"{path.name}: {region_name} must only contain grouped items")
                        for index, item in enumerate(region["items"], 1):
                            self.assertEqual(item.get("itemIndex"), index)
                            self.assertTrue({"coord", "imageElements", "textElements", "priceElements", "auxiliaryElements", "visibleStatus"}.issubset(item))

    def test_golden_calibration_tools_are_not_imported_by_production_runner(self) -> None:
        runner = (PROJECT_DIR / "phase2-card-annotation" / "scripts" / "run_phase2_recognition.py").read_text(encoding="utf-8")
        self.assertNotIn("calibrate_golden_element_contract", runner)
        self.assertNotIn("extract_golden_contract_evidence", runner)

    def test_all_34_goldens_pass_the_fail_closed_element_audit(self) -> None:
        spec = importlib.util.spec_from_file_location("validate_golden_element_contract", GOLDEN_ELEMENT_VALIDATOR_PATH)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.audit()
        self.assertTrue(result["valid"], result["errors"][:20])
        self.assertEqual(result["goldenFiles"], 34)
        self.assertEqual(result["cards"], 135)

    def test_golden_titles_and_downhangs_do_not_regress_to_clipped_ocr(self) -> None:
        results = PROJECT_DIR / "phase2-card-annotation" / "golden-sample-results"

        def nested_elements(value):
            if isinstance(value, dict):
                if "elementType" in value:
                    yield value
                for child in value.values():
                    yield from nested_elements(child)
            elif isinstance(value, list):
                for child in value:
                    yield from nested_elements(child)

        all_text = []
        for path in results.rglob("*.elements.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for element in nested_elements(payload):
                semantic_type = str(element.get("elementType", ""))
                if "标题" in semantic_type or semantic_type.startswith("下挂"):
                    self.assertNotEqual(element.get("source"), "local_crop_ocr", path.name)
                all_text.append(str(element.get("visibleText", "")))
        self.assertNotIn("士专麻心关正", all_text)

        pressure = results / "merchant-text-hang" / "商家卡片-文下挂-搜索词为解压体验馆.elements.json"
        payload = json.loads(pressure.read_text(encoding="utf-8"))
        result_list = next(item for item in payload["pageStructure"]["components"] if item.get("componentType") == "results_list")
        titles = [
            next(element["visibleText"] for element in card["regions"]["标题区"]["elements"] if element["elementType"] == "商家标题")
            for card in result_list["components"]
        ]
        self.assertEqual(len(titles), 5)
        self.assertEqual(titles[2:5], ["沐云·影院足道·奢颜SPA", "煜坤影院足道·SPA", "初初与晚晚·踩背馆·私享 SPA（麒麟社"])

    def test_hema_first_card_keeps_four_column_item_ownership(self) -> None:
        path = PROJECT_DIR / "phase2-card-annotation" / "golden-sample-results" / "merchant-graphic-hang" / "盒马.elements.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        result_list = next(item for item in payload["pageStructure"]["components"] if item.get("componentType") == "results_list")
        items = result_list["components"][0]["regions"]["下挂商品区"]["items"]
        observed = [
            (
                item["imageElements"][0]["coord"],
                item["textElements"][0]["visibleText"],
                item["priceElements"][0]["visibleText"],
                item["visibleStatus"],
            )
            for item in items
        ]
        self.assertEqual(observed, [
            ([227, 923, 264, 264], "盒马 左旋肉碱水 960ml", "¥10 限1件", "confirmed"),
            ([504, 923, 264, 264], "黄瓜 约600g", "¥3.23 限1件", "confirmed"),
            ([781, 923, 264, 264], "盒马 红豆薏米水 900ml", "¥8.51 限1件", "confirmed"),
            ([1058, 923, 166, 264], "国产富士...粒装 约6...", "¥13.44 限...", "naturally_cropped"),
        ])

    def test_face_cleaning_first_card_keeps_three_independent_colored_tags(self) -> None:
        path = PROJECT_DIR / "phase2-card-annotation" / "golden-sample-results" / "merchant-text-hang" / "商家卡片-文下挂-搜索词为面部清洁.elements.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        result_list = next(item for item in payload["pageStructure"]["components"] if item.get("componentType") == "results_list")
        tags = result_list["components"][0]["regions"]["标签区"]["elements"]
        self.assertEqual(
            [(item["visibleText"], item["coord"], item["visual"]["colorRole"]) for item in tags],
            [
                ("医疗资质", [311, 1015, 158, 46], "green"),
                ("放心美验真", [482, 1017, 200, 44], "orange"),
                ("神券最高膨至300", [696, 1016, 311, 44], "red"),
            ],
        )

    def test_all_golden_elements_publish_phase3_facing_visual_facts(self) -> None:
        results = PROJECT_DIR / "phase2-card-annotation" / "golden-sample-results"
        for path in results.rglob("*.elements.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            stack = [payload["pageStructure"]]
            while stack:
                value = stack.pop()
                if isinstance(value, dict):
                    if "elementType" in value:
                        self.assertIsInstance(value.get("render"), dict, path.name)
                        self.assertIsInstance(value.get("visual"), dict, path.name)
                        if value["visual"].get("entityKind") != "image":
                            self.assertIsInstance(value.get("textFacts"), dict, path.name)
                            self.assertIn("colorEvidence", value["visual"])
                    stack.extend(value.values())
                elif isinstance(value, list):
                    stack.extend(value)

    def test_mixue_heterogeneous_downhang_and_published_ocr_cleanup(self) -> None:
        results = PROJECT_DIR / "phase2-card-annotation" / "golden-sample-results"
        serialized = "".join(path.read_text(encoding="utf-8") for path in results.rglob("*.elements.json"))
        self.assertNotIn('"ocrConfidence"', serialized)
        self.assertNotIn('"visibleText": "江湖串吧"', serialized)

        def assert_evidence_has_no_text(value):
            if isinstance(value, dict):
                if isinstance(value.get("boundedEvidence"), list):
                    self.assertTrue(all("text" not in item for item in value["boundedEvidence"]))
                for child in value.values():
                    assert_evidence_has_no_text(child)
            elif isinstance(value, list):
                for child in value:
                    assert_evidence_has_no_text(child)
        for path in results.rglob("*.elements.json"):
            assert_evidence_has_no_text(json.loads(path.read_text(encoding="utf-8")))

        payload = json.loads((results / "merchant-graphic-hang" / "蜜雪冰城.elements.json").read_text(encoding="utf-8"))
        result_list = next(item for item in payload["pageStructure"]["components"] if item.get("componentType") == "results_list")
        first, second = result_list["components"]
        first_items = first["regions"]["下挂商品区"]["items"]
        self.assertEqual(
            [([e["visibleText"] for e in item["textElements"]], [e["visibleText"] for e in item["priceElements"]], item["visibleStatus"]) for item in first_items],
            [
                (["冰鲜柠檬水"], ["¥11"], "confirmed"),
                (["满杯百香果"], ["¥13.46 30天低价"], "confirmed"),
                (["冰鲜柠檬水"], ["¥0.8 神券价"], "confirmed"),
                (["心想事“橙..."], ["¥25..."], "naturally_cropped"),
            ],
        )
        heterogeneous = second["regions"]["下挂商品区"]["items"]
        self.assertEqual(len(heterogeneous), 4)
        self.assertEqual(heterogeneous[0]["itemType"], "异构下挂")
        self.assertEqual(heterogeneous[0]["textElements"][0]["visibleText"], "【茶山季必喝】四 ¥16")
        self.assertEqual(heterogeneous[0]["priceElements"], [])
        self.assertEqual(
            [
                (
                    item["itemType"],
                    [value["visibleText"] for value in item["textElements"]],
                    [value["visibleText"] for value in item["priceElements"]],
                    [value["visibleText"] for value in item["auxiliaryElements"]],
                    item["visibleStatus"],
                )
                for item in heterogeneous[1:]
            ],
            [
                ("常规图文下挂", ["【手作冰淇..."], ["¥10.8"], ["¥18"], "confirmed"),
                ("常规图文下挂", ["【抹茶奶茶..."], ["¥24.8"], ["¥28"], "confirmed"),
                ("常规图文下挂", [], [], [], "naturally_cropped"),
            ],
        )

    def test_validator_accepts_every_current_taxonomy_card_type_and_region(self) -> None:
        validator = load_validator_module()
        taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
        taxonomy_card_types = {item["name"] for item in taxonomy["cardTypes"]}
        taxonomy_regions = {
            region["name"]
            for item in taxonomy["cardTypes"]
            for region in item["regions"]
        }
        self.assertTrue(taxonomy_card_types <= validator.CARD_TYPES)
        self.assertTrue(taxonomy_regions <= validator.REGION_NAMES)

    def test_recognition_contracts_cover_taxonomy_and_fallbacks(self) -> None:
        taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
        contracts = json.loads(RECOGNITION_CONTRACTS_PATH.read_text(encoding="utf-8"))
        taxonomy_ids = {item["id"] for item in taxonomy["cardTypes"]}
        contract_ids = {item["cardType"] for item in contracts["contracts"]}
        self.assertEqual(taxonomy_ids, contract_ids)
        self.assertIn("广告卡", contract_ids)
        self.assertIn("异构卡", contract_ids)
        vocabulary = set(contracts["featureVocabulary"])
        for contract in contracts["contracts"]:
            self.assertTrue(contract["boundaryStrategy"])
            self.assertTrue(contract["minimumEvidenceGroups"])
            self.assertTrue(contract["requiredRegions"])
            referenced = {feature for group in contract["minimumEvidenceGroups"] for feature in group}
            referenced.update(contract.get("supportingFeatures", []))
            referenced.update(contract.get("forbiddenFeatures", []))
            self.assertTrue(referenced <= vocabulary, f"{contract['cardType']} has undefined features: {referenced - vocabulary}")
        type_specific_boundaries = {
            "商品卡片": "product_repeat_boundary",
            "商家卡片_图文下挂": "merchant_graphic_boundary",
            "商家卡片_文字下挂": "merchant_text_boundary",
            "酒店卡片": "hotel_list_boundary",
            "演出电影卡片": "performance_poster_boundary",
            "度假酒店套餐卡片": "package_bundle_boundary",
        }
        by_type = {item["cardType"]: item for item in contracts["contracts"]}
        for card_type, boundary_feature in type_specific_boundaries.items():
            self.assertTrue(any(boundary_feature in group for group in by_type[card_type]["minimumEvidenceGroups"]), card_type)

    def test_learned_geometry_profiles_exclude_broken_or_partial_goldens(self) -> None:
        payload = json.loads(GEOMETRY_PROFILES_PATH.read_text(encoding="utf-8"))
        profiles = {item["cardType"]: item for item in payload["profiles"]}
        self.assertEqual(set(profiles), {"商品卡片", "商家卡片_图文下挂", "商家卡片_文字下挂", "酒店卡片", "演出电影卡片"})
        for card_type in ("商品卡片", "商家卡片_图文下挂", "商家卡片_文字下挂", "演出电影卡片"):
            profile = profiles[card_type]
            self.assertEqual(profile["status"], "learned")
            self.assertGreater(profile["cardCount"], 0)
            self.assertGreater(profile["excludedCardCount"], 0)
            self.assertEqual(profile["excludedReasons"], {"naturallyCropped": profile["excludedCardCount"]})
            self.assertGreaterEqual(profile["distributions"]["heightRatio"]["minimum"], 0.05)
            self.assertLessEqual(profile["distributions"]["heightRatio"]["maximum"], 0.45)
            self.assertLessEqual(profile["distributions"]["aspectRatio"]["maximum"], 8.0)
        self.assertEqual(profiles["酒店卡片"]["status"], "learned")
        self.assertEqual(profiles["酒店卡片"]["excludedReasons"], {"naturallyCropped": 5})

    def test_legacy_golden_json_has_no_out_of_screenshot_geometry_or_confidence_fields(self) -> None:
        """Historical training artifacts must not retain invalid OCR facts."""
        results = PROJECT_DIR / "phase2-card-annotation" / "golden-sample-results"
        for path in sorted(results.rglob("*.json")):
            with self.subTest(path=path.relative_to(PROJECT_DIR)):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertNotIn('"confidence"', path.read_text(encoding="utf-8"))
                screenshot = Path(payload["screenshot"])
                self.assertTrue(screenshot.is_file())
                with Image.open(screenshot) as image:
                    width, height = image.size

                def check(value):
                    if isinstance(value, dict):
                        coord = value.get("coord")
                        if isinstance(coord, list) and len(coord) == 4:
                            self.assertGreater(coord[2], 0)
                            self.assertGreater(coord[3], 0)
                            self.assertGreaterEqual(coord[0], 0)
                            self.assertGreaterEqual(coord[1], 0)
                            self.assertLessEqual(coord[0] + coord[2], width)
                            self.assertLessEqual(coord[1] + coord[3], height)
                        for child in value.values():
                            check(child)
                    elif isinstance(value, list):
                        for child in value:
                            check(child)

                check(payload)


if __name__ == "__main__":
    unittest.main()
