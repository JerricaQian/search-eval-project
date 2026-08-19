from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
EXAMPLE = PROJECT_DIR / "phase2-card-annotation/references/phase2_atomic_manifest.v3.example.json"
VALIDATOR = PROJECT_DIR / "phase2-card-annotation/scripts/validate_atomic_manifest_v3.py"
GOLDEN_ROOT = PROJECT_DIR / "phase2-card-annotation/golden-atomic-v3"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_atomic_manifest_v3_test", VALIDATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AtomicManifestV3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_validator()
        cls.example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_example_is_valid_and_module_only_components_are_counted(self) -> None:
        result = self.module.validate(self.example)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["moduleCount"], 10)
        self.assertEqual(result["moduleTypeCounts"]["search_bar"], 1)
        self.assertEqual(result["moduleTypeCounts"]["page_tab"], 1)
        self.assertEqual(result["moduleTypeCounts"]["location_filter"], 1)
        self.assertEqual(result["moduleTypeCounts"]["sort_filter"], 1)
        self.assertEqual(result["moduleTypeCounts"]["price_filter"], 1)
        self.assertEqual(result["moduleTypeCounts"]["coupon_filter"], 1)
        self.assertEqual(result["moduleTypeCounts"]["instant_filter"], 1)
        self.assertEqual(result["moduleTypeCounts"]["promotion_filter"], 1)

    def test_title_affix_enums_match_the_declared_taxonomy(self) -> None:
        taxonomy = json.loads((PROJECT_DIR / "phase2-card-annotation/references/search_card_taxonomy.v1.json").read_text(encoding="utf-8"))
        product = next(card for card in taxonomy["cardTypes"] if card["id"] == "商品卡片")
        merchant_region = next(region for region in product["regions"] if region["id"] == "merchant")
        self.assertEqual(
            self.module.FULFILLMENT_TAG_VALUES,
            set(taxonomy["commonElementVocabulary"]["fulfillment"]),
        )
        self.assertEqual(
            self.module.MERCHANT_TAG_VALUES,
            set(merchant_region["elementDefinitions"]["merchantTag"]["values"]),
        )

    def test_module_slots_must_reference_owned_elements(self) -> None:
        payload = copy.deepcopy(self.example)
        payload["modulesById"]["M-search"]["slots"] = {"query": ["C1-E1"]}
        result = self.module.validate(payload)
        self.assertFalse(result["valid"])
        self.assertTrue(any("elements_must_be_owned_exactly_once" in error for error in result["errors"]))

    def test_media_rejects_redundant_is_photo_and_text(self) -> None:
        payload = copy.deepcopy(self.example)
        payload["elementsById"]["C2-E1"]["isPhoto"] = True
        payload["elementsById"]["C2-E1"]["text"] = ""
        result = self.module.validate(payload)
        self.assertFalse(result["valid"])
        self.assertTrue(any("isPhoto" in error for error in result["errors"]))
        self.assertTrue(any("media_must_not_repeat_text" in error for error in result["errors"]))

    def test_example_is_grounded_in_the_real_durian_delivery_page(self) -> None:
        self.assertEqual(self.example["source"]["viewport"], [1224, 2700])
        self.assertEqual(
            self.example["source"]["sha256"],
            "9e78421a2cb7f4dd14c282ecd33a32879f96346d76c522876fec2b1eade2d507",
        )
        module_types = {module["type"] for module in self.example["modulesById"].values()}
        self.assertNotIn("primary_point", module_types)
        self.assertEqual(
            {card["cardType"] for card in self.example["cardsById"].values()},
            {"merchant_product_card"},
        )
        image_filter = self.example["modulesById"]["M-image-filter"]
        self.assertEqual([tab["text"] for tab in image_filter["tabs"]], ["品种", "形态类型"])
        filter_labels = [
            self.example["elementsById"][f"F1-E{index}"]["text"]
            for index in (2, 4, 6, 8, 10)
        ]
        self.assertEqual(filter_labels, ["金枕", "黑刺", "托曼尼", "干尧", "青尼"])
        visible_text = {element.get("text") for element in self.example["elementsById"].values()}
        for fact in ("¥65", "¥97.5", "月售26", "48分钟", "4.0km", "79减16", "坏必赔", "免配送费"):
            self.assertIn(fact, visible_text)

    def test_element_semantics_live_in_owner_slots_not_repeated_role_fields(self) -> None:
        self.assertTrue(all("role" not in element for element in self.example["elementsById"].values()))
        price_slots = self.example["regionsById"]["C1-R3"]["slots"]
        self.assertEqual(price_slots["price_current"], ["C1-E6"])
        self.assertEqual(price_slots["price_original"], ["C1-E8"])

    def test_retained_batch_contains_only_34_latest_valid_goldens(self) -> None:
        index = json.loads((GOLDEN_ROOT / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["totals"]["images"], 34)
        self.assertEqual(index["totals"]["cards"], 135)
        self.assertEqual(index["totals"]["titleAffixes"], 130)
        self.assertEqual(index["totals"]["titleAffixErrors"], 0)
        manifests = list(GOLDEN_ROOT.rglob("*.atomic.v3.json"))
        audits = list(GOLDEN_ROOT.rglob("*.atomic.v3.audit.json"))
        self.assertEqual(len(manifests), 34)
        self.assertEqual(audits, [])
        self.assertTrue(all(self.module.validate(json.loads(path.read_text(encoding="utf-8")))["valid"] for path in manifests))

    def test_batch_durian_uses_verified_coordinates_and_no_redundant_roles(self) -> None:
        path = PROJECT_DIR / "phase2-card-annotation/golden-atomic-v3/product-card/榴莲.atomic.v3.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["cardsById"]["C1"]["bounds"], [0, 1077, 1224, 393])
        self.assertEqual(payload["cardsById"]["C2"]["bounds"], [0, 1511, 1224, 518])
        self.assertEqual(payload["cardsById"]["C4"]["visibility"], "naturally_cropped")
        delivery_time = next(element for element in payload["elementsById"].values() if element.get("text") == "48分钟")
        self.assertEqual(delivery_time["bounds"], [1068, 1222, 126, 46])
        first_regions = [payload["regionsById"][region_id] for region_id in payload["cardsById"]["C1"]["regionIds"]]
        head_media = next(region for region in first_regions if region["name"] == "head_media")
        title = next(region for region in first_regions if region["name"] == "title")
        self.assertEqual([payload["elementsById"][element_id]["text"] for element_id in head_media["slots"]["product_attribute_tag"]], ["时令"])
        self.assertEqual([payload["elementsById"][element_id]["text"] for element_id in title["slots"]["fulfillment_tag"]], ["外卖"])
        forbidden = {"role", "semanticRole", "isPhoto", "sourceRegion", "ownerRegion", "countDecision", "dedupDecision"}
        self.assertTrue(all(not (forbidden & set(element)) for element in payload["elementsById"].values()))

    def test_phase3_loader_expands_atomic_v3_without_prepublishing_eval_groups(self) -> None:
        scripts_dir = PROJECT_DIR / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        loader_spec = importlib.util.spec_from_file_location("phase2_atomic_loader_test", scripts_dir / "phase2_bundle_loader.py")
        compare_spec = importlib.util.spec_from_file_location("phase3_atomic_compare_test", scripts_dir / "extract_phase3_comparability.py")
        relation_spec = importlib.util.spec_from_file_location("phase3_atomic_relations_test", scripts_dir / "extract_phase3_relation_candidates.py")
        assert loader_spec and loader_spec.loader and compare_spec and compare_spec.loader and relation_spec and relation_spec.loader
        loader = importlib.util.module_from_spec(loader_spec)
        loader_spec.loader.exec_module(loader)
        compare = importlib.util.module_from_spec(compare_spec)
        compare_spec.loader.exec_module(compare)
        relations = importlib.util.module_from_spec(relation_spec)
        relation_spec.loader.exec_module(relations)
        path = PROJECT_DIR / "phase2-card-annotation/golden-atomic-v3/product-card/榴莲.atomic.v3.json"
        facts = loader.load_phase2_facts(manifest_path=path)
        self.assertEqual(len(facts["cards"]), 4)
        self.assertTrue(all("comparisonGroupKey" not in card["structure"] for card in facts["cards"]))
        comparison = compare.derive_comparability(facts)
        self.assertEqual(len(comparison["cardGroups"]), 1)
        self.assertTrue(comparison["comparisons"])
        candidates = relations.derive_relation_candidates(facts)
        self.assertEqual(len(candidates["authenticityCandidates"]), 4)
        scenic_path = PROJECT_DIR / "phase2-card-annotation/golden-atomic-v3/merchant-text-hang/商家卡片-文下挂-搜索词为漂流.atomic.v3.json"
        scenic_facts = loader.load_phase2_facts(manifest_path=scenic_path)
        scenic_tag = next(
            element
            for card in scenic_facts["cards"] for region in card["regions"] for element in region["elements"]
            if element.get("textFacts", {}).get("rawText") == "4A"
        )
        self.assertEqual(scenic_tag["visual"]["entityKind"], "tag")
        self.assertEqual(scenic_tag["textFacts"]["semanticRole"], "scenic_rating")

    def test_title_suffix_enums_are_separate_pixel_grounded_atoms(self) -> None:
        path = PROJECT_DIR / "phase2-card-annotation/golden-atomic-v3/merchant-text-hang/商家卡片-文下挂-搜索词为漂流.atomic.v3.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        regions = [payload["regionsById"][region_id] for region_id in payload["cardsById"]["C2"]["regionIds"]]
        title = next(region for region in regions if region["name"] == "title")
        title_element = payload["elementsById"][title["slots"]["title"][0]]
        rating_element = payload["elementsById"][title["slots"]["scenic_rating_tag"][0]]
        self.assertEqual((title_element["text"], title_element["bounds"]), ("北京欢乐谷", [410, 1167, 236, 42]))
        self.assertEqual((rating_element["text"], rating_element["bounds"]), ("4A", [656, 1176, 45, 29]))
        self.assertEqual(rating_element["kind"], "tag")

    def test_every_tag_uses_a_tag_suffixed_slot(self) -> None:
        for path in (PROJECT_DIR / "phase2-card-annotation/golden-atomic-v3").rglob("*.atomic.v3.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            elements = payload["elementsById"]
            owners = list(payload["modulesById"].values()) + list(payload["filterItemsById"].values())
            for region in payload["regionsById"].values():
                owners.append(region)
                owners.extend(region.get("items", []))
            for owner in owners:
                for role, ids in owner.get("slots", {}).items():
                    for element_id in ids:
                        if elements[element_id]["kind"] == "tag":
                            self.assertTrue(role.endswith("_tag"), (path, role, element_id))

    def test_taxonomy_hash_is_a_required_publication_gate(self) -> None:
        payload = copy.deepcopy(self.example)
        payload["taxonomy"]["sha256"] = "0" * 64
        result = self.module.validate(payload)
        self.assertFalse(result["valid"])
        self.assertIn("taxonomy.sha256_mismatch", result["errors"])

    def test_title_tag_enum_misclassification_is_rejected(self) -> None:
        payload = copy.deepcopy(self.example)
        payload["elementsById"]["C2-E7"]["text"] = "时令"
        result = self.module.validate(payload)
        self.assertFalse(result["valid"])
        self.assertTrue(any("fulfillment_tag_enum_invalid" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
