from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "scripts" / "validate_eval_results.py"


def load_module():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("validate_json_structure_evals_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class ValidateJsonStructureEvalsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_partition_positive_json_gap_is_clear_without_pixel_measurement(self) -> None:
        active = {
            "L1": {"coord": [10, 10, 100, 20]},
            "T1": {"coord": [10, 40, 80, 20]},
        }
        row = {
            "evidenceSource": "phase2_json_coordinates",
            "partitions": [
                {"region": "location", "elementIds": ["L1"], "contentBounds": [10, 10, 100, 20]},
                {"region": "tags", "elementIds": ["T1"], "contentBounds": [10, 40, 80, 20]},
            ],
            "adjacentBoundaryChecks": [{
                "firstRegion": "location",
                "secondRegion": "tags",
                "axis": "vertical",
                "gapPx": 10,
                "clear": True,
                "evidenceSource": "phase2_json_coordinates",
            }],
            "excludedPairs": [],
            "issueCount": 0,
            "rating": "优秀",
        }
        errors: list[str] = []
        self.module.require_partition_json_evidence(errors, "eval-6/C1", row, active)
        self.assertEqual(errors, [])

    def test_partition_rejects_relative_gap_or_pixel_measurement(self) -> None:
        active = {
            "L1": {"coord": [10, 10, 100, 20]},
            "T1": {"coord": [10, 40, 80, 20]},
        }
        row = {
            "evidenceSource": "phase2_json_coordinates",
            "partitions": [
                {"region": "location", "elementIds": ["L1"], "contentBounds": [10, 10, 100, 20]},
                {"region": "tags", "elementIds": ["T1"], "contentBounds": [10, 40, 80, 20]},
            ],
            "adjacentBoundaryChecks": [{
                "firstRegion": "location", "secondRegion": "tags", "axis": "vertical",
                "gapPx": 15, "clear": False, "evidenceSource": "phase2_json_coordinates",
            }],
            "excludedPairs": [],
            "issueCount": 1,
            "rating": "不达标",
            "measurement": {"tool": "forbidden"},
        }
        errors: list[str] = []
        self.module.require_partition_json_evidence(errors, "eval-6/C1", row, active)
        self.assertTrue(any("pixel_measurement_forbidden" in error for error in errors))
        self.assertTrue(any("gapPx_must_equal_10" in error for error in errors))
        self.assertTrue(any("clear_must_equal_true" in error for error in errors))

    def test_partition_overlapping_unions_are_excluded_not_failed(self) -> None:
        active = {
            "PHOTO": {"coord": [10, 10, 100, 100]},
            "BADGE_TITLE": {"coord": [90, 10, 100, 30]},
        }
        row = {
            "evidenceSource": "phase2_json_coordinates",
            "partitions": [
                {"region": "head_media", "elementIds": ["PHOTO"], "contentBounds": [10, 10, 100, 100]},
                {"region": "title", "elementIds": ["BADGE_TITLE"], "contentBounds": [90, 10, 100, 30]},
            ],
            "adjacentBoundaryChecks": [],
            "excludedPairs": [{
                "firstRegion": "head_media", "secondRegion": "title",
                "gapX": -20, "gapY": -30,
                "reason": "overlapping_or_nested_content_unions_do_not_prove_unclear_partition",
            }],
            "issueCount": 0,
            "rating": "优秀",
        }
        errors: list[str] = []
        self.module.require_partition_json_evidence(errors, "eval-6/C1", row, active)
        self.assertEqual(errors, [])

    def test_alignment_relations_are_recomputed_from_json_coordinates(self) -> None:
        active = {
            "C1-H": {"coord": [0, 0, 80, 120]},
            "C1-T": {"coord": [100, 0, 100, 30]},
            "C1-P": {"coord": [100, 80, 100, 30]},
            "C2-H": {"coord": [0, 150, 80, 120]},
            "C2-T": {"coord": [100, 150, 100, 30]},
            "C2-P": {"coord": [100, 230, 100, 30]},
        }

        def signature(card: str, offset: int) -> dict:
            return {
                "componentId": card,
                "layoutMode": "左图右文",
                "layoutSignature": "head_media:left_of:title;title:above:price",
                "regions": [
                    {"region": "head_media", "elementIds": [f"{card}-H"], "contentBounds": [0, offset, 80, 120]},
                    {"region": "title", "elementIds": [f"{card}-T"], "contentBounds": [100, offset, 100, 30]},
                    {"region": "price", "elementIds": [f"{card}-P"], "contentBounds": [100, offset + 80, 100, 30]},
                ],
                "relations": [
                    {"fromRegion": "head_media", "toRegion": "title", "relation": "left_of"},
                    {"fromRegion": "title", "toRegion": "price", "relation": "above"},
                ],
            }

        row = {
            "evidenceSource": "phase2_json_coordinates",
            "members": ["C1", "C2"],
            "layoutSignatures": [signature("C1", 0), signature("C2", 150)],
            "readingOrderChecks": [
                {"componentId": "C1", "regionOrder": ["head_media", "title", "price"], "status": "consistent"},
                {"componentId": "C2", "regionOrder": ["head_media", "title", "price"], "status": "consistent"},
            ],
            "rating": "优秀",
        }
        errors: list[str] = []
        self.module.require_alignment_json_evidence(errors, "eval-2/group", row, active)
        self.assertEqual(errors, [])

    def test_component_colour_is_validated_from_json_evidence_without_measurement(self) -> None:
        active = {"E1": {"coord": [0, 0, 20, 20]}, "E2": {"coord": [20, 0, 20, 20]}}
        row = {
            "evidenceSource": "phase2_json_visual_colors",
            "scannedElementIds": ["E1"],
            "excludedElementIds": ["E2"],
            "sourceColorValues": [
                {"elementId": "E1", "field": "textColor", "value": "#FF6600", "colorFamily": "橙"}
            ],
            "colorFamilies": ["橙"],
            "colorFamilyCount": 1,
            "rating": "优秀",
        }
        errors: list[str] = []
        self.module.require_component_color_json_evidence(errors, "eval-3/C1", row, active)
        self.assertEqual(errors, [])

    def test_component_colour_four_families_is_excellent(self) -> None:
        active = {f"E{index}": {"coord": [index * 20, 0, 20, 20]} for index in range(1, 5)}
        families = ["红", "黄", "绿", "蓝"]
        row = {
            "evidenceSource": "phase2_json_visual_colors",
            "scannedElementIds": list(active),
            "excludedElementIds": [],
            "sourceColorValues": [
                {"elementId": f"E{index}", "field": "textColor", "value": value, "colorFamily": family}
                for index, (family, value) in enumerate(zip(families, ("#FF0000", "#FFFF00", "#00FF00", "#0000FF")), start=1)
            ],
            "colorFamilies": families,
            "colorFamilyCount": 4,
            "rating": "优秀",
        }
        errors: list[str] = []
        self.module.require_component_color_json_evidence(errors, "eval-3/C4", row, active)
        self.assertEqual(errors, [])
        row["rating"] = "达标"
        self.module.require_component_color_json_evidence(errors, "eval-3/C4", row, active)
        self.assertTrue(any("rating_must_be_优秀" in error for error in errors))

    def test_page_colour_uses_the_union_of_component_families(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "component-color-families.json"
            artifact.write_text("{}", encoding="utf-8")
            c1_areas = {"红": 11, "橙": 0, "黄": 0, "绿": 0, "青": 0, "蓝": 5, "紫": 0}
            c2_areas = {"红": 0, "橙": 0, "黄": 0, "绿": 0, "青": 0, "蓝": 6, "紫": 0}
            page_areas = {"红": 11, "橙": 0, "黄": 0, "绿": 0, "青": 0, "蓝": 11, "紫": 0}
            row = {
                "colorLogicContractVersion": "3.1",
                "componentColorArtifact": str(artifact),
                "componentColorSummaries": [
                    {
                        "componentId": "C1", "colorFamilies": ["红", "蓝", "黄"], "colorFamilyCount": 3,
                        "effectiveUiPixelCount": 100, "colorFamilyPixelAreas": c1_areas,
                        "dominantColorMeasurementStatus": "measured",
                    },
                    {
                        "componentId": "C2", "colorFamilies": ["蓝", "橙", "绿"], "colorFamilyCount": 3,
                        "effectiveUiPixelCount": 100, "colorFamilyPixelAreas": c2_areas,
                        "dominantColorMeasurementStatus": "measured",
                    },
                ],
                "colorFamilies": ["红", "蓝", "黄", "橙", "绿"],
                "colorFamilyCount": 5,
                "dominantColorAreaRatioThreshold": 0.05,
                "effectiveUiPixelCount": 200,
                "colorFamilyPixelAreas": page_areas,
                "colorFamilyAreaRatios": {family: value / 200 for family, value in page_areas.items()},
                "dominantColorFamilies": ["红", "蓝"],
                "dominantColorCount": 2,
                "evidenceSource": "component_color_family_aggregation",
                "rating": "优秀",
            }
            errors: list[str] = []
            self.module.require_page_color_component_aggregation(errors, "eval-3/page", row)
        self.assertEqual(errors, [])

    def test_page_colour_thresholds_are_five_six_and_seven(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "component-color-families.json"
            artifact.write_text("{}", encoding="utf-8")
            families = ["红", "橙", "黄", "绿", "青", "蓝", "紫"]
            areas = {"红": 20, "橙": 0, "黄": 0, "绿": 0, "青": 0, "蓝": 0, "紫": 0}
            row = {
                "colorLogicContractVersion": "3.1",
                "componentColorArtifact": str(artifact),
                "componentColorSummaries": [
                    {
                        "componentId": "C1", "colorFamilies": families, "colorFamilyCount": 7,
                        "effectiveUiPixelCount": 100, "colorFamilyPixelAreas": areas,
                        "dominantColorMeasurementStatus": "measured",
                    },
                ],
                "colorFamilies": families,
                "colorFamilyCount": 7,
                "dominantColorAreaRatioThreshold": 0.05,
                "effectiveUiPixelCount": 100,
                "colorFamilyPixelAreas": areas,
                "colorFamilyAreaRatios": {family: value / 100 for family, value in areas.items()},
                "dominantColorFamilies": ["红"],
                "dominantColorCount": 1,
                "evidenceSource": "component_color_family_aggregation",
                "rating": "不达标",
            }
            errors: list[str] = []
            self.module.require_page_color_component_aggregation(errors, "eval-3/page", row)
            self.assertEqual(errors, [])
            row["colorFamilyCount"] = 6
            row["colorFamilies"] = families[:6]
            row["componentColorSummaries"][0]["colorFamilies"] = families[:6]
            row["componentColorSummaries"][0]["colorFamilyCount"] = 6
            row["rating"] = "达标"
            errors = []
            self.module.require_page_color_component_aggregation(errors, "eval-3/page", row)
        self.assertEqual(errors, [])

    def test_page_dominant_colour_thresholds_are_one_to_two_three_and_zero_or_four(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "component-color-families.json"
            artifact.write_text("{}", encoding="utf-8")
            def row_for(areas: dict[str, int], dominant: list[str], rating: str) -> dict:
                return {
                    "colorLogicContractVersion": "3.1",
                    "componentColorArtifact": str(artifact),
                    "componentColorSummaries": [{
                        "componentId": "C1", "colorFamilies": ["红", "橙", "黄"], "colorFamilyCount": 3,
                        "effectiveUiPixelCount": 100, "colorFamilyPixelAreas": areas,
                        "dominantColorMeasurementStatus": "measured",
                    }],
                    "colorFamilies": ["红", "橙", "黄"], "colorFamilyCount": 3,
                    "dominantColorAreaRatioThreshold": 0.05,
                    "effectiveUiPixelCount": 100, "colorFamilyPixelAreas": areas,
                    "colorFamilyAreaRatios": {family: value / 100 for family, value in areas.items()},
                    "dominantColorFamilies": dominant, "dominantColorCount": len(dominant),
                    "evidenceSource": "component_color_family_aggregation", "rating": rating,
                }
            three = {"红": 6, "橙": 6, "黄": 6, "绿": 0, "青": 0, "蓝": 0, "紫": 0}
            errors: list[str] = []
            self.module.require_page_color_component_aggregation(errors, "eval-3/page", row_for(three, ["红", "橙", "黄"], "达标"))
            self.assertEqual(errors, [])
            zero = {"红": 5, "橙": 5, "黄": 5, "绿": 0, "青": 0, "蓝": 0, "紫": 0}
            errors = []
            self.module.require_page_color_component_aggregation(errors, "eval-3/page", row_for(zero, [], "不达标"))
            self.assertEqual(errors, [])
            four = {"红": 6, "橙": 6, "黄": 6, "绿": 6, "青": 0, "蓝": 0, "紫": 0}
            errors = []
            self.module.require_page_color_component_aggregation(errors, "eval-3/page", row_for(four, ["红", "橙", "黄", "绿"], "不达标"))
            self.assertEqual(errors, [])

    def test_direct_json_skill_rejects_obsolete_measurement(self) -> None:
        row = {
            "evidenceSource": "phase2_json_cross_card_comparison",
            "measurement": {"tool": "obsolete"},
        }
        errors: list[str] = []
        self.module.require_json_derived_evidence(
            errors, "eval-6/page", row, "phase2_json_cross_card_comparison"
        )
        self.assertTrue(any("measurement_forbidden" in error for error in errors))

    def test_single_element_colour_uses_pixel_result_after_json_prefilter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mask = Path(tmp) / "mask.png"
            mask.write_bytes(b"debug")
            row = {
                "elementId": "E1",
                "componentId": "C1",
                "phase2Boundary": [1, 2, 30, 20],
                "sampleMask": str(mask),
                "rawColorGrid": [{"key": "orange", "ratio": 25.0}],
                "colorCount": 1,
                "rating": "优秀",
            }
            errors: list[str] = []
            self.module.require_single_element_color_pixel_evidence(
                errors, "eval-2/E1", row, {"E1": {"coord": [1, 2, 30, 20]}}
            )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
