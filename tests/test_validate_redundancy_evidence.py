from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "scripts" / "validate_eval_results.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_eval_results_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ValidateRedundancyEvidenceTest(unittest.TestCase):
    def test_component_empty_candidates_cannot_prove_excellent_without_scan(self) -> None:
        module = load_module()
        errors: list[str] = []
        module.require_zero_redundancy_scan(errors, "component", {
            "rating": "优秀", "duplicateCount": 0, "candidatePairs": [],
        }, "component")
        self.assertIn("component:excellent_zero_redundancy_requires_completed_scanCoverage", errors)

    def test_component_completed_scan_allows_excellent_zero_result(self) -> None:
        module = load_module()
        errors: list[str] = []
        module.require_zero_redundancy_scan(errors, "component", {
            "rating": "优秀", "duplicateCount": 0, "candidatePairs": [],
            "selfRepeatCandidates": [], "duplicates": [],
            "examinedElements": ["T1", "B1"], "scannedRegions": ["标题区", "标签区"],
            "scanCoverage": {
                "status": "completed", "textAtomCount": 2,
                "scannedElementIds": ["T1", "B1"], "scannedRegions": ["标题区", "标签区"],
                "crossChecks": sorted(module.COMPONENT_REDUNDANCY_CROSS_CHECKS),
            },
        }, "component")
        self.assertEqual(errors, [])

    def test_component_positive_result_requires_traceable_duplicates(self) -> None:
        module = load_module()
        errors: list[str] = []
        module.require_zero_redundancy_scan(errors, "component", {
            "rating": "不达标", "duplicateCount": 1, "candidatePairs": [],
            "selfRepeatCandidates": [],
            "duplicates": [{
                "leftElementId": "T1", "rightElementId": "B1",
                "lexicalCue": "same_numeric_attribute", "normalizedFact": "麦汁浓度=10P",
                "verdict": "duplicate", "noLossReason": "删除重复基础信息不损失新信息",
            }],
            "examinedElements": ["T1", "B1"], "scannedRegions": ["标题区", "基础信息区"],
            "scanCoverage": {
                "status": "completed", "textAtomCount": 2,
                "scannedElementIds": ["T1", "B1"], "scannedRegions": ["标题区", "基础信息区"],
                "crossChecks": sorted(module.COMPONENT_REDUNDANCY_CROSS_CHECKS),
            },
        }, "component")
        self.assertEqual(errors, [])

    def test_component_positive_result_rejects_untraceable_count(self) -> None:
        module = load_module()
        errors: list[str] = []
        module.require_zero_redundancy_scan(errors, "component", {
            "rating": "不达标", "duplicateCount": 1, "candidatePairs": [],
            "selfRepeatCandidates": [], "duplicates": [],
            "examinedElements": ["T1"], "scannedRegions": ["标题区"],
            "scanCoverage": {
                "status": "completed", "textAtomCount": 1,
                "scannedElementIds": ["T1"], "scannedRegions": ["标题区"],
                "crossChecks": sorted(module.COMPONENT_REDUNDANCY_CROSS_CHECKS),
            },
        }, "component")
        self.assertIn("component:duplicateCount_must_match_duplicates", errors)

    def test_page_empty_candidates_cannot_prove_excellent_without_pair_coverage(self) -> None:
        module = load_module()
        errors: list[str] = []
        module.require_zero_redundancy_scan(errors, "page", {
            "rating": "优秀", "redundancyCount": 0, "candidatePairs": [],
            "pageRegions": ["图筛", "结果列表"],
            "scanCoverage": {
                "status": "completed", "scannedRegionIds": ["图筛", "结果列表"], "crossChecks": [],
            },
        }, "page")
        self.assertIn("page:scanCoverage_crossChecks_must_cover_page_region_pairs", errors)


if __name__ == "__main__":
    unittest.main()
