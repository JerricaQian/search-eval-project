from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
PHASE3_DIR = PROJECT_DIR / "phase3-evaluation"
CATALOG = json.loads((PHASE3_DIR / "catalog.json").read_text(encoding="utf-8"))


class Phase3SkillContractsTest(unittest.TestCase):
    def test_all_nineteen_skills_have_a_fixed_review_flow(self) -> None:
        skills = sorted(PHASE3_DIR.glob("dimensions/*/skills/eval-*/SKILL.md"))
        self.assertEqual(len(skills), 19)
        for skill in skills:
            content = skill.read_text()
            self.assertIn("## 固定评审流程", content, skill)
            self.assertIn("## Phase2", content, skill)
            self.assertIn("## 判定标准", content, skill)
            self.assertIn("## Gotchas", content, skill)

    def test_each_dimension_contract_requires_common_phase3_knowledge(self) -> None:
        entry = PHASE3_DIR / "SKILL.md"
        index = PHASE3_DIR / "common" / "references" / "knowledge-index.md"
        self.assertTrue(entry.is_file())
        self.assertTrue(index.is_file())
        for item in CATALOG["dimensions"]:
            contract = PHASE3_DIR / item["contract"]
            content = contract.read_text()
            self.assertIn("Phase3", content, contract)
            self.assertIn("知识索引", content, contract)
            self.assertIn("固定流程", content, contract)

    def test_catalog_matches_exactly_nineteen_leaf_skills(self) -> None:
        declared = []
        for item in CATALOG["dimensions"]:
            skills_dir = PHASE3_DIR / item["skillsDir"]
            declared.extend((item["id"], skill) for skill in item["skills"])
            self.assertEqual(
                set(item["skills"]),
                {path.parent.name for path in skills_dir.glob("eval-*/SKILL.md")},
            )
        self.assertEqual(len(declared), 19)

    def test_info_comparability_defines_concrete_difference_dimensions(self) -> None:
        skill = PHASE3_DIR / "dimensions" / "page-framework" / "skills" / "eval-6-info-comparability" / "SKILL.md"
        content = skill.read_text(encoding="utf-8")
        for term in (
            "格式口径",
            "位置锚点",
            "样式语义",
            "实质影响门槛",
            "实际数值不同",
            "not_material",
        ):
            self.assertIn(term, content, skill)

    def test_pipeline_project_script_references_exist(self) -> None:
        pipeline = PROJECT_DIR / ".claude/agents/phase2345-query-pipeline.md"
        content = pipeline.read_text(encoding="utf-8")
        project_relative = set(re.findall(r"\$\{projectDir\}/([^`\"'\s]+\.py)", content))
        shared_scripts = set(re.findall(r"(?<![\w/])(scripts/[A-Za-z0-9_./-]+\.py)", content))
        referenced = project_relative | shared_scripts
        self.assertTrue(referenced)
        missing = sorted(path for path in referenced if not (PROJECT_DIR / path).is_file())
        self.assertEqual(missing, [], f"pipeline references missing project scripts: {missing}")
        for obsolete in (
            "build_phase3_atomic_fact_pack.py",
            "validate_phase3_atomic_fact_pack.py",
            "prepare_phase3_skill_run.py",
            "route_phase3_validation_failure.py",
        ):
            self.assertNotIn(obsolete, content)


if __name__ == "__main__":
    unittest.main()
