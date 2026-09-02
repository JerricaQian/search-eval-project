from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "scripts" / "validate_eval_results.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_rating_enum_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Phase3RatingEnumTest(unittest.TestCase):
    def test_component_row_retention_modes_are_disjoint_and_complete(self) -> None:
        module = load_module()
        self.assertEqual(module.COMPONENT_PROBLEM_ONLY_SKILLS, {
            "eval-1-supply-completeness",
            "eval-6-info-partitioning",
        })
        self.assertEqual(module.COMPONENT_FULL_COVERAGE_SKILLS, {
            "eval-2-visual-order-alignment",
            "eval-3-color-logic",
            "eval-4-element-complexity",
            "eval-5-info-hierarchy",
            "eval-7-info-authenticity",
            "eval-8-info-redundancy",
        })
        self.assertFalse(module.COMPONENT_PROBLEM_ONLY_SKILLS & module.COMPONENT_FULL_COVERAGE_SKILLS)

    def test_three_level_skill_accepts_declared_rating(self) -> None:
        module = load_module()
        errors: list[str] = []
        module.require_supported_rating(
            errors,
            "eval-2-color-logic-single-element/全部",
            "phase3-single_element-eval",
            "eval-2-color-logic-single-element",
            {"rating": "达标"},
        )
        self.assertEqual(errors, [])

    def test_declared_rating_does_not_require_a_score_field(self) -> None:
        module = load_module()
        errors: list[str] = []
        module.require_supported_rating(
            errors,
            "eval-1-supply-quality-scanner/全部",
            "phase3-single_element-eval",
            "eval-1-supply-quality-scanner",
            {"rating": "不达标"},
        )
        self.assertEqual(errors, [])

    def test_two_level_skill_rejects_invented_pass_rating(self) -> None:
        module = load_module()
        errors: list[str] = []
        module.require_supported_rating(
            errors,
            "eval-1-supply-quality-scanner/全部",
            "phase3-single_element-eval",
            "eval-1-supply-quality-scanner",
            {"rating": "达标"},
        )
        self.assertEqual(errors, [
            "eval-1-supply-quality-scanner/全部:rating_not_defined_in_skill_weight:达标"
        ])

    def test_block_style_weight_frontmatter_is_supported(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "eval-block-weight"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: eval-block-weight\ntitle: 块式权重\nweight:\n  优秀: 1\n  达标: 0\n  不达标: -1\naggregate: test\n---\n",
                encoding="utf-8",
            )
            original = module.SKILL_DIRECTORIES["phase3-single_element-eval"]
            module.SKILL_DIRECTORIES["phase3-single_element-eval"] = Path(tmp)
            try:
                self.assertEqual(
                    module.load_skill_weight("phase3-single_element-eval", "eval-block-weight"),
                    {"优秀": 1.0, "达标": 0.0, "不达标": -1.0},
                )
            finally:
                module.SKILL_DIRECTORIES["phase3-single_element-eval"] = original


if __name__ == "__main__":
    unittest.main()
