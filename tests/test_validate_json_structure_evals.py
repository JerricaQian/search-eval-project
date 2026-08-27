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
