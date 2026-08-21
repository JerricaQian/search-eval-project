from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


PROJECT_DIR = Path(__file__).resolve().parents[1]
CLI_PATH = PROJECT_DIR / "workflow" / "eval_cli.py"


class PortableTaskProtocolTest(unittest.TestCase):
    def prepare(self, root: Path, run_id: str = "portable-01") -> dict:
        source = root / "external"
        project = root / "project"
        source.mkdir()
        Image.new("RGB", (100, 100), "white").save(source / "露营_全部_1.png")
        completed = subprocess.run(
            [
                sys.executable, str(CLI_PATH), "prepare-evaluate",
                "--project-dir", str(project), "--source-dir", str(source),
                "--query", "露营", "--min-bytes", "1", "--run-id", run_id,
            ],
            check=True, capture_output=True, text=True,
        )
        return json.loads(completed.stdout)

    def test_prepare_creates_immutable_task_and_rejects_duplicate_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self.prepare(root)
            portable = payload["portableTask"]
            task_path = Path(portable["taskPath"])
            task = json.loads(task_path.read_text())

            self.assertEqual(portable["protocol"], "MEITUAN_EVAL_TASK_V2")
            self.assertEqual(task["runId"], "portable-01")
            self.assertEqual(task["workflowArgs"]["tag"], "portable-01")
            self.assertEqual(task["workflowArgs"]["batchId"], "portable-01")
            self.assertEqual(task["workflowArgs"]["rerunId"], "portable-01")

            source = root / "external"
            project = root / "project"
            repeated = subprocess.run(
                [
                    sys.executable, str(CLI_PATH), "prepare-evaluate",
                    "--project-dir", str(project), "--source-dir", str(source),
                    "--query", "露营", "--min-bytes", "1", "--run-id", "portable-01",
                ],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(repeated.returncode, 2)
            self.assertEqual(json.loads(repeated.stdout)["status"], "run_setup_failed")

    def test_finalize_accepts_only_complete_verified_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = self.prepare(root)
            project = root / "project"
            task_path = Path(payload["portableTask"]["taskPath"])
            result_path = Path(payload["portableTask"]["resultPath"])

            manifest = project / "screenshots-out" / "elements.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}")
            manifest_audit = project / "screenshots-out" / "elements.audit.json"
            manifest_audit.write_text('{"valid": true}')
            eval_result = project / ".artifacts" / "eval-results.json"
            eval_result.parent.mkdir(parents=True)
            eval_result.write_text("[]")
            eval_audit = project / ".artifacts" / "eval-audit.json"
            eval_audit.write_text('{"valid": true}')
            report = project / "reports" / "report.html"
            report.parent.mkdir(parents=True)
            report.write_text("<html></html>")
            result_path.write_text(json.dumps({
                "ok": True,
                "query": "露营",
                "stageA": {"elementListPaths": [str(manifest)], "elementAuditPaths": [str(manifest_audit)]},
                "stageB": {"evalResultFile": str(eval_result), "evalAuditFile": str(eval_audit)},
                "stageC": {"evidenceImages": []},
                "stageD": {"reportPath": str(report)},
                "blockedAt": "",
                "error": "",
            }, ensure_ascii=False))

            completed = subprocess.run(
                [sys.executable, str(CLI_PATH), "finalize-evaluate", "--task", str(task_path), "--result", str(result_path)],
                check=True, capture_output=True, text=True,
            )
            receipt = json.loads(completed.stdout)
            self.assertEqual(receipt["status"], "completed")
            self.assertTrue(Path(receipt["receiptPath"]).is_file())

    def test_finalize_rejects_success_without_all_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = self.prepare(Path(tmp))
            task_path = Path(payload["portableTask"]["taskPath"])
            result_path = Path(payload["portableTask"]["resultPath"])
            result_path.write_text(json.dumps({"ok": True, "query": "露营", "blockedAt": "", "error": ""}))

            completed = subprocess.run(
                [sys.executable, str(CLI_PATH), "finalize-evaluate", "--task", str(task_path), "--result", str(result_path)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("successful_result_missing_stage", json.loads(completed.stdout)["error"])

