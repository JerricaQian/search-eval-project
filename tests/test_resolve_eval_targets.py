from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
RESOLVER = PROJECT_DIR / "phase3-evaluation-officer" / "scripts" / "resolve_eval_targets.py"


def run_selection(selection: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RESOLVER),
            "--project-dir",
            str(PROJECT_DIR),
            "--selection-json",
            json.dumps(selection, ensure_ascii=False),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


class ResolveEvalTargetsTest(unittest.TestCase):
    def test_full_19_resolves_every_canonical_skill(self) -> None:
        completed = run_selection({"mode": "full_19"})
        self.assertEqual(completed.returncode, 0, completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["coverage"], {
            "selectedCount": 19,
            "fullCount": 19,
            "isFull": True,
            "label": "完整19项评测",
        })
        self.assertEqual(len(payload["evalTargets"]), 19)
        self.assertEqual(payload["dimensions"], [
            "phase3-single_element-eval",
            "phase3-card_or_component-eval",
            "phase3-page_framework-eval",
        ])

    def test_dimension_and_custom_selection_preserve_scope(self) -> None:
        dimension = run_selection({"mode": "dimensions", "dimensions": ["phase3-card_or_component-eval"]})
        self.assertEqual(dimension.returncode, 0, dimension.stdout)
        self.assertEqual(json.loads(dimension.stdout)["coverage"]["selectedCount"], 8)

        custom = run_selection({
            "mode": "custom_skills",
            "skills": [
                {"dimension": "phase3-card_or_component-eval", "skill": "eval-8-info-redundancy"},
                {"dimension": "phase3-card_or_component-eval", "skill": "eval-7-info-authenticity"},
            ],
        })
        self.assertEqual(custom.returncode, 0, custom.stdout)
        payload = json.loads(custom.stdout)
        self.assertEqual(payload["coverage"]["selectedCount"], 2)
        self.assertFalse(payload["coverage"]["isFull"])
        self.assertEqual([target["skill"] for target in payload["evalTargets"]], [
            "eval-8-info-redundancy",
            "eval-7-info-authenticity",
        ])

    def test_unknown_skill_is_rejected_instead_of_falling_back(self) -> None:
        completed = run_selection({
            "mode": "custom_skills",
            "skills": [{"dimension": "phase3-card_or_component-eval", "skill": "eval-404"}],
        })
        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("evaluationSelection_skill_unknown", payload["error"])


if __name__ == "__main__":
    unittest.main()
