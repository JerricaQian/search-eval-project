from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DIMENSIONS = {
    "phase3-single_element-eval": "单一元素评测通用契约.md",
    "phase3-card_or_component-eval": "组件卡片评测通用契约.md",
    "phase3-page_framework-eval": "页面框架评测通用契约.md",
}


class Phase3SkillContractsTest(unittest.TestCase):
    def test_all_nineteen_skills_have_a_fixed_review_flow(self) -> None:
        skills = sorted(PROJECT_DIR.glob("phase3-*-eval/eval-skills/eval-*/SKILL.md"))
        self.assertEqual(len(skills), 19)
        for skill in skills:
            content = skill.read_text()
            self.assertIn("## 固定评审流程", content, skill)
            self.assertIn("## Phase2", content, skill)
            self.assertIn("## 判定标准", content, skill)
            self.assertIn("## Gotchas", content, skill)

    def test_each_dimension_contract_requires_the_evaluation_officer_knowledge(self) -> None:
        officer = PROJECT_DIR / "phase3-evaluation-officer" / "SKILL.md"
        index = PROJECT_DIR / "phase3-evaluation-officer" / "references" / "knowledge-index.md"
        self.assertTrue(officer.is_file())
        self.assertTrue(index.is_file())
        for dimension, contract_name in DIMENSIONS.items():
            contract = PROJECT_DIR / dimension / contract_name
            content = contract.read_text()
            self.assertIn("Phase3 评测官", content, contract)
            self.assertIn("知识索引", content, contract)
            self.assertIn("固定流程", content, contract)


if __name__ == "__main__":
    unittest.main()
