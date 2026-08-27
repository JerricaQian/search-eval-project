from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "scripts" / "validate_eval_results.py"


def load_module():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("validate_eval_results_complexity_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class ValidateElementComplexityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.ledger = [
            {
                "elementId": "E1",
                "region": "rating_and_reason",
                "content": "服务很好非常喜欢",
                "decision": "included_tag",
                "reason": "无容器彩色辅助文字",
                "styleKey": "tag|orange|recommendation|none|none",
            },
            {
                "elementId": "E2",
                "region": "price",
                "content": "¥375起",
                "decision": "excluded",
                "reason": "主价格不是标签",
            },
        ]
    def valid_row(self) -> dict:
        return {
            "componentId": "C1",
            "expectedRegions": ["rating_and_reason", "price"],
            "scannedRegions": ["rating_and_reason", "price"],
            "unscannedRegions": [],
            "scannedElementIds": ["E1", "E2"],
            "candidateLedger": self.ledger,
            "phase2ReviewCandidates": [],
            "coverageStatus": "completed",
            "evidenceSource": "phase2_json_visual_inventory",
            "includedTagStyles": [{
                "elementIds": ["E1"],
                "content": "服务很好非常喜欢",
                "styleKey": "tag|orange|recommendation|none|none",
                "countDecision": "计入",
                "dedupDecision": "同键去重",
            }],
        }

    def test_complete_whole_card_coverage_is_directly_auditable(self) -> None:
        errors: list[str] = []
        self.module.require_complexity_coverage(errors, "eval-4/C1", self.valid_row())
        self.assertEqual(errors, [])

    def test_json_derived_complexity_rejects_measurement(self) -> None:
        row = self.valid_row()
        row["measurement"] = {"tool": "obsolete"}
        errors: list[str] = []
        self.module.require_json_derived_evidence(
            errors, "eval-4/C1", row, "phase2_json_visual_inventory"
        )
        self.assertTrue(any("measurement_forbidden" in error for error in errors))

    def test_missing_region_is_rejected(self) -> None:
        row = self.valid_row()
        row["scannedRegions"] = ["price"]
        errors: list[str] = []
        self.module.require_complexity_coverage(errors, "eval-4/C1", row)
        self.assertTrue(any("scannedRegions_must_cover_expectedRegions" in error for error in errors))

    def test_phase2_review_candidate_blocks_formal_rating(self) -> None:
        row = self.valid_row()
        row["phase2ReviewCandidates"] = [{"coord": [0, 0, 20, 20]}]
        errors: list[str] = []
        self.module.require_complexity_coverage(errors, "eval-4/C1", row)
        self.assertTrue(any("phase2_review_required_blocks_formal_rating" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
