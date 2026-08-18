from __future__ import annotations

import json
import importlib.util
import unittest
from pathlib import Path

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = PROJECT_DIR / "scripts" / "validate_element_manifest.py"
TAXONOMY_PATH = PROJECT_DIR / "phase2-card-annotation" / "references" / "search_card_taxonomy.v1.json"
RECOGNITION_CONTRACTS_PATH = PROJECT_DIR / "phase2-card-annotation" / "references" / "card_recognition_contracts.v1.json"
GEOMETRY_PROFILES_PATH = PROJECT_DIR / "phase2-card-annotation" / "references" / "learned_card_geometry_profiles.v1.json"


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

        expected_result_card_type = {"演出卡.elements.json": "演出卡", "电影卡.elements.json": "电影影院卡"}
        for name, card_type in expected_result_card_type.items():
            with self.subTest(path=name):
                payload = json.loads((results / "performance-movie-card" / name).read_text(encoding="utf-8"))
                components = payload["pageStructure"]["components"]
                self.assertEqual([component["componentType"] for component in components[:2]], ["search_bar", "tab"])
                result_list = next(component for component in components if component["componentType"] == "results_list")
                self.assertGreater(len(result_list["components"]), 0)
                self.assertTrue(all(card["cardType"] == card_type for card in result_list["components"]))

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
        self.assertEqual(set(profiles), {"商品卡片", "商家卡片_图文下挂", "商家卡片_文字下挂", "演出电影卡片"})
        self.assertEqual(profiles["演出电影卡片"]["status"], "unavailable")
        self.assertEqual(profiles["演出电影卡片"]["excludedReasons"], {"missingCoord": 4})
        for card_type in ("商品卡片", "商家卡片_图文下挂", "商家卡片_文字下挂"):
            profile = profiles[card_type]
            self.assertEqual(profile["status"], "learned")
            self.assertGreater(profile["cardCount"], 0)
            self.assertGreater(profile["excludedCardCount"], 0)
            self.assertGreaterEqual(profile["distributions"]["heightRatio"]["minimum"], 0.05)
            self.assertLessEqual(profile["distributions"]["heightRatio"]["maximum"], 0.45)
            self.assertLessEqual(profile["distributions"]["aspectRatio"]["maximum"], 8.0)

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
